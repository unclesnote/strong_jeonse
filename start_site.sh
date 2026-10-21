#!/usr/bin/env bash
# 지도 사이트와 청약 경쟁률 백엔드를 실행한다(.venv의 Python, 표준 라이브러리 서버).
# 사이트마다 서버가 따로 뜨므로 여러 사이트를 동시에 실행할 수 있다(포트 자동 배정).
#
#   ./start_site.sh                  사이트가 하나면 바로, 여러 개면 번호로 선택(포그라운드)
#   ./start_site.sh 2                목록의 2번 사이트
#   ./start_site.sh lh-runs/<실행>/site/dist
#   ./start_site.sh 2 --bg           백그라운드로 실행하고 주소만 출력(로그: tmp/logs/)
#   ./start_site.sh --all            실행 중이 아닌 모든 사이트를 백그라운드로 실행
#   ./start_site.sh --list           사이트 목록·실행 상태·주소 출력
#   ./start_site.sh 2 --restart      이미 실행 중이면 묻지 않고 중지 후 다시 시작(포트 유지)
#   ./start_site.sh 2 --stop         선택한 사이트의 서버만 중지
#   ./start_site.sh --stop-all       목록에 있는 모든 사이트의 서버 중지
#   옵션: --port N(기본 8765, 사용 중이면 다음 빈 포트) --bind ADDR --runs-dir DIR(기본 lh-runs, 반복 가능)
#
# 같은 사이트가 이미 실행 중이면 재시작·중지·그대로 두기 중에서 묻는다. 터미널이 아니면 묻지 않고
# 실행 중인 주소만 알리고 종료한다(--restart/--stop으로 지정).
# 어느 경우든 접속 주소(http://…/)를 한 줄에 전체로 출력한다.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/project_env.sh"
cd "$ROOT"

PORT=8765 PORT_SET=0 BIND=127.0.0.1 CHOICE="" LIST=0 ACTION="" BG=0 ALL=0 STOP_ALL=0 RUNS_DIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; PORT_SET=1; shift 2 ;; --bind) BIND="$2"; shift 2 ;;
    --runs-dir) RUNS_DIRS+=("$2"); shift 2 ;; --list) LIST=1; shift ;;
    --restart) ACTION=restart; shift ;; --stop) ACTION=stop; shift ;;
    --bg) BG=1; shift ;; --all) ALL=1; BG=1; shift ;; --stop-all) STOP_ALL=1; shift ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    -*) die "알 수 없는 옵션: $1" ;;
    *) CHOICE="$1"; shift ;;
  esac
done
[ "${#RUNS_DIRS[@]}" -gt 0 ] || RUNS_DIRS=("${LH_RUNS_DIR:-lh-runs}")

# 서버는 표준 라이브러리만 쓰므로 .venv가 없으면 패키지 설치 없이 바로 만든다.
if ! venv_ok; then
  warn ".venv가 없거나 손상되어 새로 만듭니다. 새 공고 빌드까지 하려면 ./setup_env.sh를 실행하세요."
  make_venv
fi

# 사이트별 서버·캐시 위치. 실행 폴더 사이트는 그 실행의 backend/와 tmp/competition/을 쓰고,
# 작업공간 사이트는 data/runtime/을 쓴다. 사이트마다 캐시가 분리되어 서로 덮지 않는다.
site_paths() {
  if [ "$1" = "$ROOT/public" ]; then STATE="$ROOT/data/runtime"; SERVER="$ROOT/backend/server.py"; LOGNAME_=public
  else
    local run; run="$(dirname "$(dirname "$1")")"; STATE="$run/tmp/competition"; LOGNAME_="$(basename "$run")"
    SERVER="$run/backend/server.py"; [ -f "$SERVER" ] || SERVER="$ROOT/backend/server.py"
  fi
}
free_port() {
  "$PY" - "$BIND" "$1" <<'EOF'
import socket, sys
bind, port = sys.argv[1], int(sys.argv[2])
for p in range(port, port + 50):
    with socket.socket() as s:
        # 서버(http.server)와 같이 SO_REUSEADDR로 검사해야 TIME_WAIT 포트를 사용 중으로 오인하지 않는다.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind((bind, p)); print(p); break
        except OSError: pass
else: sys.exit('빈 포트를 찾지 못했습니다.')
EOF
}
# 백그라운드 실행: 포트가 실제로 열릴 때까지 기다린 뒤 주소를 출력한다.
start_bg() {
  local site="$1" port="$2" log pid i
  site_paths "$site"; mkdir -p "$ROOT/tmp/logs"; log="$ROOT/tmp/logs/site-$LOGNAME_.log"
  # setsid: 실행한 터미널·세션이 닫혀도 서버가 같이 종료되지 않도록 새 세션에서 띄운다.
  local detach=(); command -v setsid >/dev/null && detach=(setsid)
  "${detach[@]}" nohup "$PY" "$SERVER" --directory "$site" --state-dir "$STATE" --port "$port" --bind "$BIND" >"$log" 2>&1 </dev/null &
  pid=$!
  for i in $(seq 50); do
    kill -0 "$pid" 2>/dev/null || { warn "시작 실패: ${site#"$ROOT"/} (로그: ${log#"$ROOT"/})"; tail -3 "$log" >&2; return 1; }
    "$PY" -c 'import socket,sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), 0.2).close()' "$BIND" "$port" 2>/dev/null && break
    sleep 0.1
  done
  printf '%s   (PID %s · %s · 로그 %s)\n' "$(url_of "$BIND" "$port")" "$pid" "${site#"$ROOT"/}" "${log#"$ROOT"/}"
}

load_sites
if [ "$LIST" = 1 ]; then show; exit 0; fi

if [ "$STOP_ALL" = 1 ]; then
  pids=()
  for s in "${SITES[@]}"; do running_of "${s%%$'\t'*}" && for r in "${RUNNING[@]}"; do pids+=("${r%%$'\t'*}"); done; done
  [ "${#pids[@]}" -gt 0 ] || { say "실행 중인 사이트 서버가 없습니다."; exit 0; }
  stop_servers "${pids[@]}"; say "모든 사이트 서버를 중지했습니다."; exit 0
fi

if [ "$ALL" = 1 ]; then
  say "모든 사이트를 백그라운드로 실행합니다. 브라우저에서 아래 주소를 여세요(복사해서 사용):"
  next="$PORT"
  for s in "${SITES[@]}"; do
    site="${s%%$'\t'*}"
    if running_of "$site"; then
      IFS=$'\t' read -r pid _ host port <<<"${RUNNING[0]}"
      printf '%s   (PID %s · %s · 이미 실행 중)\n' "$(url_of "$host" "$port")" "$pid" "${site#"$ROOT"/}"
      continue
    fi
    port="$(free_port "$next")"; start_bg "$site" "$port" || true; next=$((port + 1))
  done
  echo "(목록: ./start_site.sh --list · 모두 중지: ./start_site.sh --stop-all)"
  exit 0
fi

if [ -z "$CHOICE" ]; then
  if [ "${#SITES[@]}" -eq 1 ]; then CHOICE=1
  elif [ -t 0 ]; then
    echo "실행할 사이트를 선택하세요(모두 실행: --all):"; show
    read -rp "번호 [1]: " CHOICE; CHOICE="${CHOICE:-1}"
  else
    echo "사이트가 여러 개입니다. 번호나 경로를 인자로 주거나 --all을 쓰세요:" >&2; show >&2; exit 2
  fi
fi
SITE="$(site_of "$CHOICE")"

# 같은 사이트를 띄운 서버가 이미 있는지 확인한다(다른 사이트 서버는 건드리지 않는다).
if running_of "$SITE"; then
  PIDS=()
  echo "이 사이트는 이미 실행 중입니다: ${SITE#"$ROOT"/}"
  for r in "${RUNNING[@]}"; do
    IFS=$'\t' read -r pid _ host port <<<"$r"; PIDS+=("$pid")
    printf '  %s   (PID %s)\n' "$(url_of "$host" "$port")" "$pid"
  done
  if [ -z "$ACTION" ]; then
    if [ -t 0 ]; then
      printf '  1) 중지 후 다시 시작\n  2) 중지만\n  3) 그대로 두고 종료\n'
      read -rp "선택 [3]: " answer
      case "${answer:-3}" in 1) ACTION=restart ;; 2) ACTION=stop ;; 3) ACTION=keep ;; *) die "1~3 중에서 선택하세요." ;; esac
    else
      ACTION=keep
    fi
  fi
  case "$ACTION" in
    keep)
      say "기존 서버를 그대로 둡니다. 브라우저에서 아래 주소를 여세요."
      for r in "${RUNNING[@]}"; do IFS=$'\t' read -r _ _ host port <<<"$r"; url_of "$host" "$port"; echo; done
      echo "(재시작: ./start_site.sh \"${SITE#"$ROOT"/}\" --restart · 중지: --stop)"
      exit 0 ;;
    stop) stop_servers "${PIDS[@]}"; say "중지했습니다. 위 주소는 더 이상 열리지 않습니다."; exit 0 ;;
    restart)
      stop_servers "${PIDS[@]}"
      # 포트를 지정하지 않았으면 기존 주소가 바뀌지 않도록 이전 포트를 그대로 쓴다.
      if [ "$PORT_SET" = 0 ]; then IFS=$'\t' read -r _ _ _ PORT <<<"${RUNNING[0]}"; fi ;;
  esac
elif [ "$ACTION" = stop ]; then
  say "실행 중인 서버가 없습니다: ${SITE#"$ROOT"/}"; exit 0
fi

PORT="$(free_port "$PORT")"
if [ "$BG" = 1 ]; then
  say "백그라운드로 실행합니다. 브라우저에서 아래 주소를 여세요(복사해서 사용):"
  start_bg "$SITE" "$PORT"; exit
fi
site_paths "$SITE"
say "사이트 시작: ${SITE#"$ROOT"/}"
say "브라우저에서 아래 주소를 여세요(복사해서 사용):"
url_of "$BIND" "$PORT"; echo
exec "$PY" "$SERVER" --directory "$SITE" --state-dir "$STATE" --port "$PORT" --bind "$BIND"
