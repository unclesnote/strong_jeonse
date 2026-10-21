# shellcheck shell=bash
# setup_env.sh·start_site.sh가 source하는 공통 설정. 직접 실행하지 않는다.
# Python은 프로젝트의 .venv만 쓰고, pip·바이트코드 캐시도 프로젝트의 tmp/ 안에 둔다.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
export PIP_CACHE_DIR="$ROOT/tmp/pip-cache"
export PYTHONPYCACHEPREFIX="$ROOT/tmp/pycache"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PYTHONNOUSERSITE=1   # ~/.local의 사용자 패키지를 섞지 않는다
export PYTHONUTF8=1
export LANG="${LANG:-C.UTF-8}"
export TZ="${TZ:-Asia/Seoul}"
mkdir -p "$PIP_CACHE_DIR" "$PYTHONPYCACHEPREFIX"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[주의]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[오류]\033[0m %s\n' "$*" >&2; exit 1; }
venv_ok() { [ -x "$PY" ] && "$PY" -c 'import sys; assert sys.version_info >= (3, 10) and sys.prefix != sys.base_prefix' 2>/dev/null; }

# venv 생성. python3-venv(ensurepip)가 없으면 pip 없이 만들고 시스템 pip로 venv 안에 pip를 넣는다.
make_venv() {
  local sys_py; sys_py="$(command -v python3)" || die "python3가 없습니다. 'sudo apt install python3' 후 다시 실행하세요."
  "$sys_py" -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null || die "Python 3.10 이상이 필요합니다: $("$sys_py" --version 2>&1)"
  rm -rf "$VENV"
  if "$sys_py" -c 'import ensurepip' 2>/dev/null; then "$sys_py" -m venv "$VENV" && return; fi
  warn "python3-venv(ensurepip)가 없어 pip 없는 venv를 만든 뒤 pip를 넣습니다."
  "$sys_py" -m venv --without-pip "$VENV" || die "venv 생성 실패. 'sudo apt install python3-venv' 후 다시 실행하세요."
  if "$sys_py" -m pip --version >/dev/null 2>&1; then
    "$sys_py" -m pip --python "$PY" install --upgrade pip || warn "venv에 pip 설치 실패(지도 서버는 pip 없이 동작합니다)."
  else
    warn "시스템 pip도 없어 venv에 pip를 넣지 못했습니다. 'sudo apt install python3-venv' 후 setup_env.sh를 다시 실행하세요(지도 서버는 pip 없이 동작합니다)."
  fi
}
venv_has_pip() { "$PY" -m pip --version >/dev/null 2>&1; }
