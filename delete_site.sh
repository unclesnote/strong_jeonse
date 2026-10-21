#!/usr/bin/env bash
# 스킬로 추가한 사이트(실행 폴더 lh-runs/<실행>/)를 선택해 삭제한다. 작업공간 사이트 public/은 삭제하지 않는다.
#
#   ./delete_site.sh              목록에서 번호 선택(여러 개는 공백으로 구분)
#   ./delete_site.sh 3 4          목록의 3·4번 삭제(확인 질문)
#   ./delete_site.sh lh-runs/<실행>/site/dist
#   ./delete_site.sh --list       목록만 출력(번호는 start_site.sh와 같다)
#   ./delete_site.sh 3 --yes      묻지 않고 삭제. 실행 중이면 중지 후 삭제
#   옵션: --runs-dir DIR(기본 lh-runs, 반복 가능)
#
# 삭제 단위는 실행 폴더 전체(사이트·원본·데이터·보고서)다. 실행 중인 사이트는 중지할지 먼저 묻고,
# 중지하지 않으면 그 사이트는 건너뛴다. git에 커밋된 파일은 삭제 후에도 git으로 복구할 수 있다.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/project_env.sh"
cd "$ROOT"

YES=0 LIST=0 CHOICES=() RUNS_DIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1; shift ;; --list) LIST=1; shift ;;
    --runs-dir) RUNS_DIRS+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) die "알 수 없는 옵션: $1" ;;
    *) CHOICES+=("$1"); shift ;;
  esac
done
[ "${#RUNS_DIRS[@]}" -gt 0 ] || RUNS_DIRS=("${LH_RUNS_DIR:-lh-runs}")
venv_ok || make_venv
INTERACTIVE=0; [ -t 0 ] && INTERACTIVE=1

load_sites
if [ "$LIST" = 1 ]; then show; exit 0; fi

if [ "${#CHOICES[@]}" -eq 0 ]; then
  [ "$INTERACTIVE" = 1 ] || { echo "삭제할 사이트 번호나 경로를 인자로 주세요:" >&2; show >&2; exit 2; }
  echo "삭제할 사이트를 선택하세요(작업공간 public/은 삭제할 수 없음):"; show
  read -rp "번호(여러 개는 공백으로, 취소는 Enter): " line
  read -ra CHOICES <<<"$line"
  [ "${#CHOICES[@]}" -gt 0 ] || { say "취소했습니다."; exit 0; }
fi

# 실행 폴더인지 엄격히 확인한다: <runs-dir>/<실행>/site/dist 이고 <runs-dir>는 지정한 runs 폴더 중 하나.
RUN_BASES=(); for d in "${RUNS_DIRS[@]}"; do [ -d "$d" ] && RUN_BASES+=("$(cd "$d" && pwd -P)"); done
run_of() {
  local site="$1" run base
  [ "$(basename "$site")" = dist ] && [ "$(basename "$(dirname "$site")")" = site ] || return 1
  run="$(cd "$(dirname "$(dirname "$site")")" && pwd -P)"
  for base in "${RUN_BASES[@]}"; do [ "$(dirname "$run")" = "$base" ] && [ "$run" != "$base" ] && { echo "$run"; return 0; }; done
  return 1
}

TARGET_SITES=() TARGET_RUNS=() TRACKED=()
for c in "${CHOICES[@]}"; do
  site="$(site_of "$c")"
  if [ "$site" = "$ROOT/public" ]; then warn "작업공간 사이트(public/)는 삭제할 수 없습니다. 건너뜀."; continue; fi
  run="$(run_of "$site")" || { warn "lh-runs의 실행 폴더 사이트가 아니라 건너뜀: $site"; continue; }
  dup=0; for r in "${TARGET_RUNS[@]}"; do [ "$r" = "$run" ] && dup=1; done
  [ "$dup" = 1 ] || { TARGET_SITES+=("$site"); TARGET_RUNS+=("$run"); }
done
[ "${#TARGET_RUNS[@]}" -gt 0 ] || { say "삭제할 사이트가 없습니다."; exit 0; }

echo "삭제 대상(실행 폴더 전체):"
for i in "${!TARGET_RUNS[@]}"; do
  run="${TARGET_RUNS[$i]}" site="${TARGET_SITES[$i]}" rel="${TARGET_RUNS[$i]#"$ROOT"/}"
  label=""; for s in "${SITES[@]}"; do [ "${s%%$'\t'*}" = "$site" ] && { IFS=$'\t' read -r _ label _ _ <<<"$s"; }; done
  printf '  - %s\n    %s · %s\n' "$rel" "$label" "$(du -sh "$run" 2>/dev/null | cut -f1)"
  if running_of "$site"; then
    for r in "${RUNNING[@]}"; do IFS=$'\t' read -r pid _ host port <<<"$r"; printf '    \033[1;32m● 실행 중\033[0m: %s (PID %s)\n' "$(url_of "$host" "$port")" "$pid"; done
  fi
  # 저장소 밖(--runs-dir로 지정한 다른 위치)이면 git 명령이 실패하므로 '커밋 없음'으로 본다.
  tracked="$( { git ls-files -- "$run" 2>/dev/null || true; } | wc -l)"
  untracked="$( { git ls-files --others --exclude-standard -- "$run" 2>/dev/null || true; } | wc -l)"
  TRACKED[$i]="$tracked"
  if [ "$tracked" -eq 0 ]; then warn "    git에 커밋되지 않은 실행입니다. 삭제하면 복구할 수 없습니다."
  elif [ "$untracked" -gt 0 ]; then warn "    git에 없는 파일 ${untracked}개는 삭제하면 복구할 수 없습니다(커밋된 ${tracked}개는 git으로 복구 가능)."
  else echo "    git에 커밋됨: 삭제 후에도 git으로 복구 가능"; fi
done

if [ "$YES" = 0 ]; then
  [ "$INTERACTIVE" = 1 ] || die "비대화형 실행에서는 --yes가 있어야 삭제합니다."
  read -rp "위 ${#TARGET_RUNS[@]}개 실행 폴더를 삭제할까요? [y/N]: " answer
  [[ "$answer" =~ ^[yY]$ ]] || { say "취소했습니다."; exit 0; }
fi

deleted=() deleted_tracked=()
for i in "${!TARGET_RUNS[@]}"; do
  run="${TARGET_RUNS[$i]}" site="${TARGET_SITES[$i]}" rel="${TARGET_RUNS[$i]#"$ROOT"/}"
  if running_of "$site"; then
    pids=(); for r in "${RUNNING[@]}"; do pids+=("${r%%$'\t'*}"); done
    if [ "$YES" = 0 ]; then
      read -rp "$rel 사이트가 실행 중입니다. 중지하고 삭제할까요? [Y/n]: " answer
      [[ "${answer:-y}" =~ ^[yY]$ ]] || { warn "실행 중이라 건너뜀: $rel"; continue; }
    fi
    stop_servers "${pids[@]}"
  fi
  rm -rf -- "$run"
  say "삭제: $rel"; deleted+=("$rel")
  [ "${TRACKED[$i]}" -eq 0 ] || deleted_tracked+=("$rel")
done

# git에 커밋돼 있던 실행을 지웠을 때만 반영·복구 방법을 안내한다.
[ "${#deleted_tracked[@]}" -gt 0 ] || exit 0
echo
echo "git에 반영하려면: git add -A lh-runs && git commit -m 'Remove notice sites' (원격까지: git push)"
echo "커밋 전 되돌리기: git checkout -- ${deleted_tracked[*]}"
