#!/usr/bin/env bash
# 한 번에 환경 구성: 시스템 도구(apt) → 프로젝트 .venv → pip 패키지 → 설치 확인 → 테스트
#
#   ./setup_env.sh              전체 구성(필요할 때만 sudo apt 실행)
#   ./setup_env.sh --no-system  apt 단계 생략(지도 보기·경쟁률만 쓸 때)
#   ./setup_env.sh --recreate   .venv를 지우고 새로 만든다
#   ./setup_env.sh --no-test    마지막 테스트 생략
#   ./setup_env.sh --upgrade    requirements가 그대로여도 pip·패키지를 다시 설치/업그레이드
#
# 여러 번 실행해도 안전하다. 기존 환경을 먼저 확인해 이미 갖춰진 단계는 건너뛴다.
#   시스템 패키지: 설치된 것은 제외   .venv: 정상이면 재사용   pip: requirements·Python 버전이 같으면 생략
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/scripts/project_env.sh"
cd "$ROOT"

SYSTEM=1 TEST=1 RECREATE=0 UPGRADE=0
for arg in "$@"; do
  case "$arg" in
    --no-system) SYSTEM=0 ;; --no-test) TEST=0 ;; --recreate) RECREATE=1 ;; --upgrade) UPGRADE=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) die "알 수 없는 옵션: $arg" ;;
  esac
done

# 1. 시스템 도구 — Poppler(PDF), LibreOffice Impress(PPTX), 한글 폰트, venv 모듈
APT_PACKAGES=(python3 python3-venv python3-pip ca-certificates poppler-utils libreoffice-impress fonts-noto-cjk fonts-liberation)
if [ "$SYSTEM" = 1 ]; then
  if command -v dpkg-query >/dev/null && command -v apt-get >/dev/null; then
    missing=()
    for p in "${APT_PACKAGES[@]}"; do
      dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || missing+=("$p")
    done
    # 정상 .venv가 이미 있으면 python3-venv는 필요 없다(매번 sudo를 묻지 않도록 제외).
    if venv_ok && venv_has_pip; then
      kept=(); for p in "${missing[@]}"; do [ "$p" = python3-venv ] || kept+=("$p"); done; missing=("${kept[@]}")
    fi
    if [ "${#missing[@]}" -eq 0 ]; then
      say "시스템 패키지: 모두 설치되어 있음"
    else
      say "시스템 패키지 설치: ${missing[*]}"
      SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
      if $SUDO apt-get update && $SUDO apt-get install -y "${missing[@]}"; then :; else
        warn "apt 설치 실패. 지도 보기·경쟁률은 계속 쓸 수 있지만 새 공고 빌드(PDF/PPTX 변환)는 실패합니다."
      fi
    fi
  else
    warn "apt가 없는 시스템입니다. Poppler·LibreOffice·한글 폰트는 직접 설치하세요(docs/ENV_SETUP.md)."
  fi
else
  say "시스템 패키지 단계 생략(--no-system)"
fi

# 2. 프로젝트 전용 가상환경 — 시스템 site-packages와 분리
if [ "$RECREATE" = 0 ] && venv_ok && venv_has_pip; then
  say "가상환경: 이미 있음 — 재사용 ($("$PY" --version 2>&1), $VENV)"
else
  if [ "$RECREATE" = 1 ]; then say "가상환경 재생성(--recreate): $VENV"
  elif [ -e "$VENV" ]; then say "가상환경이 손상되었거나 pip가 없어 다시 만듭니다: $VENV"
  else say "가상환경 생성: $VENV"; fi
  make_venv
fi
venv_ok && venv_has_pip || die "가상환경에 pip가 없습니다. 'sudo apt install python3-venv' 후 './setup_env.sh --recreate'를 실행하세요."

# 3. Python 패키지 — 캐시는 tmp/pip-cache
# requirements.txt와 Python 버전의 해시를 .venv에 기록해, 바뀌지 않았고 패키지가 온전하면 설치를 생략한다.
MARKER="$VENV/.requirements.sha256"
WANT="$( { cat config/requirements.txt; "$PY" -c 'import sys; print(sys.version)'; } | sha256sum | cut -d' ' -f1)"
if [ "$UPGRADE" = 0 ] && [ "$(cat "$MARKER" 2>/dev/null)" = "$WANT" ] && "$PY" -m pip check >/dev/null 2>&1 \
   && "$PY" -c 'import requests, bs4, PIL, jsonschema' 2>/dev/null; then
  say "Python 패키지: 이미 설치됨(requirements 변경 없음) — 건너뜀. 다시 설치하려면 --upgrade"
else
  say "Python 패키지 설치(캐시: tmp/pip-cache)"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install --upgrade -r config/requirements.txt
  echo "$WANT" > "$MARKER"
fi

# 4. 설치 확인
say "설치 확인"
"$PY" -m pip check
"$PY" - <<'EOF'
import shutil, sqlite3, sys
import requests, bs4, PIL, jsonschema
from PIL import features
print(f'  Python {sys.version.split()[0]} ({sys.prefix})')
print(f'  SQLite {sqlite3.sqlite_version} · WebP {"OK" if features.check("webp") else "없음"}')
missing = [n for n in ('pdfinfo', 'pdftoppm', 'libreoffice') if not shutil.which(n)]
print('  변환 도구: ' + ('OK' if not missing else '없음 → ' + ', '.join(missing) + ' (새 공고 빌드에만 필요)'))
EOF

# 5. 테스트
if [ "$TEST" = 1 ]; then
  say "테스트 실행"
  if ! "$PY" -m unittest discover -s tests; then
    # 사이트 보기·경쟁률에는 Poppler/LibreOffice가 필요 없다. 도구가 없어서 실패한 경우는 경고만 한다.
    if command -v pdfinfo >/dev/null && command -v pdftoppm >/dev/null && command -v libreoffice >/dev/null; then
      die "테스트 실패. 위 출력을 확인하세요."
    fi
    warn "변환 도구(Poppler·LibreOffice)가 없어 일부 테스트가 실패했습니다. 사이트 보기·경쟁률(./start_site.sh)은 사용할 수 있고, 새 공고 빌드에는 ./setup_env.sh(sudo apt)가 필요합니다."
  fi
fi

say "완료. 사이트 실행: ./start_site.sh"
