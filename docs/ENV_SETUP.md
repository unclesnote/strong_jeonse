# 개발·실행 환경 설정 — Windows / Ubuntu

## 0. 빠른 시작 — Ubuntu / WSL

git clone 직후 바로 사용할 수 있다. 필요한 것은 Python 3.10 이상과 인터넷 연결뿐이다(pip 패키지, LH 경쟁률 조회, 지도 배경).

```bash
git clone <저장소 URL> strong_jeonse && cd strong_jeonse
./setup_env.sh --no-system   # 사이트 보기만: sudo 불필요. 새 공고 빌드까지 하려면 옵션 없이 실행(sudo apt)
./start_site.sh              # 출력된 http://localhost:8765/ 열기. 여러 사이트는 --all
```

`--no-system`으로 설정했는데 Poppler·LibreOffice가 없으면, PDF 관련 테스트 실패를 경고로만 남기고 설정을 마친다. `python3-venv`와 시스템 pip가 모두 없는 PC에서는 venv에 pip를 넣을 수 없으므로 `./setup_env.sh`(apt 포함)를 실행한다. 이때도 `./start_site.sh`는 pip 없이 동작한다.

```bash
./setup_env.sh    # 시스템 도구(필요 시 sudo apt) → .venv 생성 → pip 설치 → 설치 확인 → 테스트
./start_site.sh   # 지도 사이트 + 청약 경쟁률 백엔드. 사이트가 여러 개면 번호로 선택
```

- 두 스크립트는 프로젝트의 `.venv/`만 사용한다. 시스템 site-packages와 `~/.local` 사용자 패키지를 섞지 않는다(`PYTHONNOUSERSITE=1`). pip 다운로드 캐시는 `tmp/pip-cache/`, 바이트코드 캐시는 `tmp/pycache/`(`PYTHONPYCACHEPREFIX`)에 둔다. 공통 설정은 `scripts/project_env.sh`에 있다.
- `setup_env.sh`는 기존 환경을 먼저 확인해 이미 갖춰진 단계를 건너뛴다. 설치된 apt 패키지는 제외하고, 정상 `.venv`가 있으면 `python3-venv`도 요구하지 않는다. 정상 `.venv`는 재사용한다. `requirements.txt`와 Python 버전의 해시(`.venv/.requirements.sha256`)가 같고 `pip check`·import가 통과하면 pip 단계를 생략한다. 옵션: `--no-system`(apt 생략, sudo 불필요), `--recreate`(.venv 재생성), `--upgrade`(pip·패키지 재설치/업그레이드), `--no-test`.
- `python3-venv`(ensurepip)가 없으면 pip 없는 venv를 만든 뒤 시스템 pip로 venv 안에 pip를 설치한다. 시스템 pip도 없으면 `sudo apt install python3-venv`가 필요하다.
- `start_site.sh`는 `public/`(작업공간)과 `lh-runs/*/site/dist`(실행 폴더, 최신순)를 찾는다. 하나면 바로 실행하고, 여러 개면 번호를 묻는다. 터미널이 아닐 때는 번호나 경로를 인자로 준다. `--list`, `--port N`(사용 중이면 다음 빈 포트), `--runs-dir DIR`, `--bind ADDR`을 지원한다. `.venv`가 없으면 패키지 없이 바로 만들어 실행한다. 서버는 표준 라이브러리만 사용한다.
- 사이트 삭제: `./delete_site.sh`는 같은 번호 목록에서 고른 실행 폴더 사이트(여러 개 가능)를 확인 후 삭제한다. 작업공간 `public/`은 삭제할 수 없다. 실행 중이면 중지할지 먼저 묻고 중지한 뒤 삭제한다(`--yes`는 묻지 않고 중지·삭제). git에 커밋된 실행은 git으로 복구할 수 있고, 커밋되지 않은 파일이 있으면 미리 경고한다.
- 여러 사이트 동시 운용: 사이트마다 서버가 따로 뜬다. `./start_site.sh --all`은 실행 중이 아닌 모든 사이트를 백그라운드로 띄우고, 사이트별 전체 URL을 출력한다(8765부터 빈 포트 순서). `./start_site.sh N --bg`는 한 사이트를 백그라운드로 띄운다. 로그는 `tmp/logs/site-<실행폴더명>.log`에 남는다. `./start_site.sh N --stop`은 그 사이트만, `./start_site.sh --stop-all`은 목록의 모든 사이트 서버를 중지한다.
- 공고 URL마다 빌드한 사이트는 `lh-runs/<UTC시각>-<panId>-<고유값>/`에 계속 쌓인다. 기존 실행 폴더와 작업공간 `public/`은 덮어쓰지 않는다. 같은 공고를 다시 빌드해도 새 폴더가 생긴다. 원본, 표준 데이터, 미리보기, 지오코딩 캐시, 사이트, 경쟁률 캐시(`tmp/competition/`)가 모두 실행 폴더 안에 있어 사이트끼리 상태를 공유하지 않는다. `build_notice.py`의 기본 `--runs-dir`은 실행 위치와 관계없이 프로젝트 루트의 `lh-runs/`이다(`LH_RUNS_DIR`로 변경 가능). `start_site.sh`도 같은 곳을 찾는다.
- `start_site.sh`는 실행 여부와 관계없이 접속 주소 전체(`http://localhost:8765/`)를 한 줄로 출력한다. `--list`에도 실행 중인 사이트의 주소와 PID가 나온다.
- 같은 사이트가 이미 실행 중이면 주소를 보여 주고 `1) 중지 후 다시 시작 2) 중지만 3) 그대로 두고 종료`를 묻는다(기본 3). 터미널이 아니면 묻지 않고 주소만 출력하고 종료한다. `--restart`, `--stop`으로 지정할 수 있다. 재시작할 때 `--port`가 없으면 기존 포트를 유지한다. 실행 여부는 PID 파일이 아니라 `/proc`의 `backend/server.py --directory` 인자로 판별하므로(`scripts/site_procs.py`) 수동으로 띄운 서버도 찾는다.
- 경쟁률 소스 URL은 선택한 사이트 폴더의 `competition-config.json`(`sourceUrl`)이다. 사이트 폴더마다 하나씩 있고 데이터셋의 `notice.sourceUrl`에서 생성된다. 목록과 서버 시작 메시지에 표시된다.

아래는 각 단계를 수동으로 수행하거나 문제를 해결할 때의 상세 설명이다.

이 문서는 LH 공고 수집, 주택목록 XLSX 변환, PDF·PPTX·이미지 미리보기 생성, 좌표 검증, 독립 지도 빌드 및 로컬 확인에 필요한 환경을 설명한다. 명령은 별도 표시가 없으면 `strong_jeonse` 프로젝트 최상위에서 실행한다.

## 1. 환경 선택과 실제 검증 범위

| 환경 | 사용 범위 | 이 프로젝트의 확인 상태 |
|---|---|---|
| Ubuntu 24.04 계열 / Python 3.12 | 수집부터 미리보기·데이터 검증·지도 빌드까지 | 현재 Linux 환경에서 기능·데이터·테스트 확인 |
| Windows + WSL2 + Ubuntu 24.04 | Ubuntu와 같은 전체 파이프라인 | 코드 의존성과 공식 WSL 설치 절차에 맞춘 안내. Windows 장비에서 직접 실행한 검증은 미실시 |
| Windows 기본 PowerShell + Python | 이미 완성된 `public/`의 로컬 지도·경쟁률 보기 | 표준 라이브러리 서버 `backend/server.py` 사용. Windows 실기 검증은 미실시 |

전체 빌드의 Windows 실행 경로는 WSL2다. 현재 변환 코드는 `libreoffice` 명령과 Linux 형식의 LibreOffice 프로필 URI를 사용한다. Windows의 `soffice.com` 경로를 PATH에 추가하는 것만으로 전체 파이프라인이 호환된다고 보장하지 않는다. Windows 네이티브 자동 변환은 별도 실행파일 탐색·URI 처리와 실기 검증이 필요하다. 운영체제별 LibreOffice 명령 형식은 [공식 안내](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)를 참고한다.

Ubuntu 24.04와 Python 3.12는 이 안내의 구체적인 설치 기준이다. 코드의 Python 최소 기준은 3.10이다. 다른 Ubuntu 버전에서는 설치 가능한 패키지 버전을 확인한다.

## 2. 필요한 구성요소

| 구성요소 | 역할 | 필요한 경우 |
|---|---|---|
| Python 3.10 이상, 기준 3.12 | 수집·변환·검증·HTTP 서버 | Python 도구 실행 |
| `requests` | LH 첨부·홍보물 조회, 주소 조회 | 새 자료 수집 |
| `beautifulsoup4` | LH 공고 HTML 분석 | 새 자료 수집 |
| `Pillow` | 이미지 처리, WebP 페이지와 썸네일 생성 | 미리보기 새 생성 |
| `jsonschema` 4.x | 표준 데이터 검증 | 표준 패키지 검증·빌드 |
| Poppler `pdfinfo`, `pdftoppm` | PDF 페이지 수 확인, 이미지 렌더링 | PDF 검증·미리보기 생성 |
| LibreOffice Impress | PPTX를 PDF로 변환 | PPTX 미리보기 생성 |
| 한글 폰트 | 변환 과정의 한글 글리프 표시 | PPTX 렌더링 |
| Chrome / Edge 등 브라우저 | 지도 UI, 브라우저 확인·수집 보조 | 화면 확인 |
| Git | 프로젝트 소스 복제·이력 관리 | Git으로 소스를 받는 경우 |

Python 패키지의 지원 범위는 [`config/requirements.txt`](../config/requirements.txt)에 모았다. 정확한 버전을 고정한 lockfile은 아니며, 설치된 버전은 별도로 기록할 수 있다.

기본 파이프라인, 지도, 경쟁률 로컬 백엔드에는 Node.js, npm, 별도 데이터베이스 서버, Excel, Google Maps API 키가 필요하지 않다. 경쟁률 캐시는 Python 내장 SQLite를 쓴다. Node.js는 호스팅 Worker 빌드(`scripts/build_hosted.mjs`)와 JS 파서 대조 테스트에만 쓰이며, 없으면 해당 테스트는 생략된다. Leaflet 자산은 `public/vendor/`에 들어 있다. 지도 배경 타일은 인터넷으로 가져온다. 좌표는 빌드 시 공개 주소 검색으로 확인해 JSON에 보관하며, 화면을 열 때 재지오코딩하지 않는다. 외부 서비스의 접근 정책이 바뀌면 해당 단계를 재확인해야 한다.

`build_lh.mjs`는 기존 환경의 `@oai/artifact-tool`을 사용하는 선택적 서식 XLSX 생성 도구다. 일반 환경에서는 [`scripts/build_inventory.py`](../scripts/build_inventory.py)가 표준 라이브러리로 정리 XLSX를 생성하며 새 공고 스킬도 이 경로를 사용한다. 기존 `node_modules` 심볼릭 링크는 다른 PC에서 그대로 작동하는 설치물이 아니다.

## 3. Ubuntu 설치

### 3.1 시스템 프로그램

Ubuntu 터미널에서 실행한다. `apt` 단계는 관리자 권한이 필요하고 Python 가상환경과 데이터 빌드는 일반 사용자로 실행한다. [Ubuntu 패키지 관리 안내](https://ubuntu.com/server/docs/how-to/software/package-management/)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates poppler-utils libreoffice-impress fonts-noto-cjk fonts-liberation
```

프로젝트 폴더를 준비한다. 이미 받은 폴더가 있으면 그 위치로 이동한다. 새 복제 시에는 실제 저장소 URL과 접근 권한을 사용한다. 이 프로젝트의 `.git` 내부 주소나 자격증명을 다른 사람에게 전달하지 않는다.

```bash
cd /실제/프로젝트/경로/strong_jeonse
python3 --version
```

위 `/실제/프로젝트/경로/strong_jeonse`는 사용자의 실제 경로로 바꾼다. 가장 쉬운 방법은 `git clone`이다. 지도(`public/`), 데이터(`data/datasets/`), 빌드한 공고 사이트(`lh-runs/`), 스킬, 테스트가 모두 저장소에 들어 있다. 폴더를 직접 복사할 때도 이 폴더들을 함께 복사한다. `.venv/`와 `tmp/`는 다른 PC에서 복사하지 않고 `./setup_env.sh`로 다시 만든다.

### 3.2 프로젝트 전용 Python 환경

```bash
# ./setup_env.sh가 아래를 모두 수행한다. 수동으로 할 때:
source scripts/project_env.sh   # 캐시 위치(tmp/)·UTF-8·TZ 설정
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r config/requirements.txt
```

새 터미널에서도 프로젝트로 이동한 후 `source .venv/bin/activate`를 실행한다. `PYTHONUTF8`, `LANG`, `TZ`는 위 명령을 실행한 셸에 적용된다. 한글 JSON·파일명 처리를 위해 UTF-8을 사용하고 수집일을 한국 날짜로 기록하려면 `TZ=Asia/Seoul`을 유지한다. 실행 폴더 이름은 코드에서 UTC 시각으로 생성한다.

가상환경은 프로젝트 안에 Python 패키지를 격리한다. 활성화가 어려운 상황에는 `.venv/bin/python`을 직접 사용할 수 있다. [Python venv 공식 문서](https://docs.python.org/3/library/venv.html)

### 3.3 설치 확인

```bash
python -m pip check
python -c "import requests, bs4, PIL, jsonschema; print('Python packages OK')"
python -c "from PIL import features; assert features.check('webp'), 'WebP support missing'; print('WebP OK')"
python -c "import shutil; print({name: shutil.which(name) for name in ['pdfinfo', 'pdftoppm', 'libreoffice']})"
pdfinfo -v
pdftoppm -v
libreoffice --version
fc-match 'Noto Sans CJK KR'
```

실행파일 조회 결과에 `None`이 없어야 한다. `fc-match` 결과는 한글 폰트 탐색 확인용이며 원본 PPTX의 전용 폰트가 그대로 재현된다는 보장은 아니다. 변환 결과에서 한글과 레이아웃을 눈으로 확인한다.

## 4. Windows 전체 빌드 — WSL2 + Ubuntu

### 4.1 WSL2 설치

Windows 11 또는 Microsoft가 WSL 간편 설치를 지원하는 Windows 10 환경에서 관리자 PowerShell을 열어 실행한다. 설치 중 재부팅이 요청되면 재부팅한다. [Microsoft WSL 설치 안내](https://learn.microsoft.com/en-us/windows/wsl/install)

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

이미 해당 배포판이 있으면 재설치하지 않고 아래 확인·실행 명령을 사용한다. 온라인 목록에 이름이 다르게 표시되면 실제 배포판 이름을 사용한다.

```powershell
wsl --list --verbose
wsl -d Ubuntu-24.04
```

`VERSION`이 2인지 확인한다. 기존 배포판이 1이면 필요한 경우 `wsl --set-version Ubuntu-24.04 2`로 변환한다. 첫 Ubuntu 실행 시 Linux 사용자 이름과 비밀번호를 만든다. 이후 설치·빌드는 **Ubuntu 터미널 안에서** 수행한다. Windows PowerShell의 `python`과 WSL Ubuntu의 `python`은 서로 다른 환경이다.

### 4.2 프로젝트 위치와 패키지 설치

예를 들어 Windows의 `C:\work\strong_jeonse`는 WSL에서 `/mnt/c/work/strong_jeonse`다. 그 폴더에서 바로 작업할 수도 있지만, 이미지 파일을 많이 생성하므로 WSL의 Linux 홈 아래에 별도 작업본을 두는 방식을 사용한다. 기존 폴더가 없는 새 대상에만 복사한다.

```bash
sudo apt update
sudo apt install -y rsync
mkdir -p ~/work
rsync -a --exclude='.venv/' --exclude='node_modules' /mnt/c/work/strong_jeonse/ ~/work/strong_jeonse/
cd ~/work/strong_jeonse
```

대상이 이미 있으면 위 복사를 반복하지 말고 기존 대상 폴더로 이동한다. 원본 Windows 폴더와 WSL 작업본은 서로 다른 복사본이므로 이후 파일 변경이 자동 동기화되지 않는다. 위 복사는 `.venv/`와 환경 전용 `node_modules`를 제외한다. Windows에서 만든 `.venv`를 WSL에서 재사용하지 않는다.

이제 **3절의 Ubuntu 시스템 패키지 설치, 가상환경 생성, Python 패키지 설치, UTF-8 설정, 설치 확인을 그대로 수행**한다. 필요한 프로그램은 WSL 안에 설치한다. Windows에 설치된 LibreOffice는 WSL의 `libreoffice` 명령을 대신하지 않는다.

Windows 브라우저에서 WSL의 로컬 웹 서버는 통상 `http://localhost:8765/`로 접속한다. 접속 문제는 [Microsoft WSL 네트워크 안내](https://learn.microsoft.com/en-us/windows/wsl/networking)를 확인한다. 먼저 WSL 안에서 같은 주소가 열리는지 확인하고, 자동 localhost 연결이 실패하면 배포판 실행 상태와 로컬 네트워크 설정을 점검한다.

### 4.3 스킬 사용 위치(Codex·Claude Code)

Codex가 이 프로젝트 폴더를 작업공간으로 열어 `.agents/skills/lh-notice-map/SKILL.md`를 읽도록 한다. WSL에서 빌드할 경우 에이전트의 셸도 WSL 환경을 사용하거나 WSL 터미널에서 아래 CLI를 직접 실행한다. 공용 사용자 스킬 폴더에 복사할 필요는 없다. Claude Code는 프로젝트 폴더를 열면 `.claude/skills/lh-notice-map/SKILL.md`를 `/lh-notice-map`으로 쓸 수 있다. 이 스킬은 공통 규칙을 Codex 스킬 파일에서 읽는다. 에이전트 설치·로그인은 사용 중인 앱의 설정에 따르며, Python CLI 빌드 자체에는 에이전트가 필요 없다.

## 5. 실행과 검증 — Ubuntu / WSL 공통

다음 명령은 가상환경을 활성화한 프로젝트 최상위에서 실행한다.

### 5.1 설치 후 기본 검증

```bash
python -m unittest discover -s tests -v
```

테스트 수는 기능 추가에 따라 늘어난다. Node.js가 없으면 호스팅용 JS 테스트 2개는 건너뛴다. 실제 PDF 페이지 검증이 포함되므로 `pdfinfo`가 필요하다. 테스트는 임시 폴더와 작은 예제 자료를 사용하며 공고를 새로 다운로드하지 않는다.

기존 실제 패키지가 있는 경우 파일·좌표·미디어 관계를 검증한다.

```bash
python scripts/dataset.py validate --dataset data/datasets/2015122300020927/dataset.json --asset-root data/datasets/2015122300020927
```

현재 공고 기준 성공 결과는 344세대·56건물 주소·62미디어·252미리보기 페이지다. 다른 공고의 정상 개수는 그 원본을 기준으로 확인한다.

### 5.2 완성된 현재 지도 보기

```bash
./start_site.sh            # 여러 사이트가 있으면 번호 선택
./start_site.sh 1          # 목록 번호로 바로 실행
```

브라우저에서 출력된 주소를 연다. 서버를 실행한 터미널을 유지하고 종료하려면 `Ctrl+C`를 누른다. 내부적으로 `.venv/bin/python backend/server.py --directory public --state-dir data/runtime`을 실행하며, 정적 파일과 `/api/competition`(30분 주기 조회), `POST /api/competition/refresh`(즉시 조회)를 함께 제공한다. `index.html`을 파일로 직접 더블클릭하면 경쟁률과 상대 링크가 동작하지 않는다.

### 5.3 새 공고를 수집해 독립 지도 만들기

실제 공고 ID가 포함된 URL을 따옴표로 감싼다. `&`가 들어 있어도 한 개의 URL 인자로 전달되어야 한다.

```bash
python scripts/build_notice.py 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=실제공고ID'   # 기본 출력: 프로젝트 루트의 lh-runs/
```

`실제공고ID`를 원문에서 확인한 숫자로 바꾼다. 기본 명령은 새 공고의 원본·홍보물 수집과 미리보기·좌표·표준 데이터·별도 사이트 생성을 수행한다. HWP/HWPX는 다운로드하지 않는다. 자료 형식이 다르거나 좌표를 확정하지 못하면 보고서를 남기고 중단한다. 수집과 공개 주소 검색 및 패키지 설치에는 인터넷이 필요하다.

스킬 실행마다 `lh-runs/<UTC시각>-<공고ID>-<고유값>/`이 생긴다. 출력의 `RUN_ROOT` 값을 확인하고 그 폴더를 사용한다. 작업공간의 `public/`과 이전 실행 폴더는 그대로 두고 새 사이트만 추가한다. 새 결과는 다음처럼 연다.

```bash
./start_site.sh            # 새 실행 폴더가 목록에 최신순으로 나타난다
./start_site.sh 'lh-runs/실제실행폴더/site/dist'
```

8765가 사용 중이면 다음 빈 포트를 자동으로 사용한다. 경쟁률 캐시는 그 실행 폴더의 `tmp/competition/`에 저장된다. 새 빌드의 `reports/run.json`이 `complete`인지 확인하고 지도 필터·목록·세대 표·PDF 이미지·원본 링크를 점검한다. 자세한 데이터 설정은 [스킬 가이드](SKILL_GUIDE.md), [공고 데이터 준비 가이드](../.agents/skills/lh-notice-map/references/DATA_GUIDE.md), [미디어 표준](../.agents/skills/lh-notice-map/references/DATA_STANDARD.md)을 따른다.

### 5.4 네트워크 수집 없이 기존 표준 패키지로 빌드

원본과 미리보기가 포함된 기존 패키지가 있다면 다음 명령으로 독립 결과를 만들 수 있다.

```bash
python scripts/build_notice.py 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300020927' --from-bundle data/datasets/2015122300020927 --runs-dir lh-runs --no-install
```

이 단계는 LH 다운로드·좌표 조회를 다시 하지 않는다. 패키지 ID·해시·페이지 관계를 재검증하며 지도 배경 타일은 여전히 인터넷 연결이 필요하다. `--no-install`은 부족한 Python 패키지를 자동 설치하지 않게 한다. 필요한 패키지는 먼저 설치해 둔다.

### 5.5 LH 사이트 직접 접근이 막히는 경우

브라우저로 같은 공고를 열어 실제 공고 ID와 기준 주택목록 파일 ID를 확인한다. 저장한 HTML과 다음 인자를 사용해 새 실행을 만든다.

```bash
python scripts/build_notice.py 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=실제공고ID' --html 'tmp/확인한공고.html' --notice-id 실제공고ID --runs-dir lh-runs
```

HTML은 해당 상세 페이지의 실제 내용을 보존해야 한다. Windows에서 저장했다면 WSL이 읽을 수 있는 경로로 옮긴다. 브라우저 조작이 필요한 단계는 에이전트의 브라우저 도구로 수행하며 CLI가 브라우저를 자동 조작하는 기능은 없다. 공고 ID 없는 URL은 `needs_browser` 보고서를 남기며 이전 공고로 추정하지 않는다. 저장한 HTML을 사용해도 홍보물 조회·첨부 다운로드에 필요한 네트워크 접근은 별도로 가능해야 한다.

## 6. Windows 기본 환경에서 완성된 지도만 보기

이 절은 WSL 없이 이미 만들어진 `public/`(작업공간 사이트)을 확인하는 용도다. 실행 폴더 사이트는 `--directory lh-runs\<실행>\site\dist --state-dir lh-runs\<실행>\tmp\competition`으로 연다. [Python Windows 공식 안내](https://docs.python.org/3/using/windows.html)를 따라 Python을 설치하고 새 PowerShell에서 `py --version`이 실행되는지 확인한다. 프로젝트를 예를 들어 `C:\work\strong_jeonse`에 준비한 후 실행한다.

```powershell
Set-Location 'C:\work\strong_jeonse'
$env:PYTHONUTF8 = '1'
py backend\server.py --directory public --state-dir data\runtime --port 8765
```

`py` 명령이 설치되어 있지 않고 `python --version`이 동작하면 `py` 대신 `python`을 사용한다. 브라우저에서 `http://localhost:8765/`를 열고 종료는 `Ctrl+C`다. 서버는 표준 라이브러리만 쓰므로 이 경우에는 pip 패키지, Poppler, LibreOffice가 필요하지 않다. 경쟁률도 함께 동작한다. 셸 스크립트(`setup_env.sh`, `start_site.sh`)는 WSL·Linux용이다.

Python 가상환경을 Windows에서 별도로 만드는 경우에는 다음처럼 실행파일을 직접 호출하면 PowerShell의 활성화 스크립트 실행 정책을 변경할 필요가 없다. 이는 Windows용 Python 환경을 만드는 방법이며 전체 변환기의 네이티브 호환을 추가하는 명령은 아니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r config\requirements.txt
```

WSL용 `.venv`와 Windows용 `.venv`를 한 경로에서 공유하지 않는다. 두 환경은 별도 프로젝트 작업본에서 생성한다.

## 7. 환경 변수·자료 보관·게시

| 설정 | 설명 |
|---|---|
| `PYTHONUTF8=1` | 명시적 인코딩이 없는 파일 처리에도 Python UTF-8 모드 적용 |
| `LANG=C.UTF-8` | Ubuntu/WSL의 UTF-8 로케일 |
| `TZ=Asia/Seoul` | Linux 실행 환경의 수집일 기준. 실행 폴더명은 UTC |
| `LH_PAN_ID`, `LH_NOTICE_HTML` | 개별 수집 스크립트용 공고 ID·입력 HTML |
| `LH_OUTPUT_ROOT`, `LH_SOURCE_ROOT` | 개별 도구의 원본 입력·저장 폴더 |
| `LH_ASSETS_DIR`, `LH_TEMP_ROOT` | 개별 변환 도구의 자산·임시 폴더 |
| `LH_SOURCE_DATA`, `LH_MANIFEST`, `LH_GEOCODES_OUTPUT`, `LH_GEOCODE_CACHE` | 개별 좌표 도구의 입력·출력·캐시 |

일반적인 새 공고 빌드에서는 `build_notice.py`가 실행별 경로를 설정하므로 `LH_*`를 수동 지정하지 않는다. 다른 PC에서 복사한 `config/active-dataset.json`의 절대 경로는 원래 PC를 가리킬 수 있으므로 새 실행 빌드에는 명시적인 `--from-bundle` 경로 등을 사용한다.

프로젝트의 문서는 `docs/`, 스크립트는 `scripts/`, 자료는 `data/`, 전달 ZIP은 `outputs/`, 가상환경은 `.venv/`, 임시는 `tmp/`에 둔다. `.venv/`와 Python 캐시는 소스 관리에서 제외한다. 파일 원본·미리보기·배포용 스냅샷을 보관하므로 원본 총크기만큼의 공간으로 끝나지 않는다. 실제 공고 사례의 원본은 약 75MB였고 표준 자산과 사이트 사본 및 ZIP은 추가 공간을 사용했다. 새 실행은 이전 폴더를 남기므로 여유 디스크를 확보한다.

로컬 빌드에는 호스팅 계정이나 자격증명이 필요하지 않다. ChatGPT Sites에 게시하려면 해당 서비스의 로그인·연결과 새 프로젝트 등록 절차가 별도로 필요하다. 새 공고 결과에는 기존 `.openai/hosting.json`이나 사이트 ID를 복사하지 않는다. 일반 정적 호스팅에 `site/dist/`만 올리면 지도는 동작하지만 경쟁률은 표시되지 않는다. 경쟁률 API에는 `backend/server.py`를 실행할 수 있는 서버나, `scripts/build_hosted.mjs`로 만드는 Worker 빌드가 필요하다.

## 8. 문제 해결

| 증상 | 확인·해결 |
|---|---|
| `ensurepip is not available`, venv 생성 실패 | `./setup_env.sh`가 pip 없는 venv + 시스템 pip로 자동 우회한다. 그래도 실패하면 `sudo apt install python3-venv` 후 `./setup_env.sh --recreate`. 다른 버전 Python이면 그 인터프리터에 맞는 venv 패키지 확인 |
| `externally-managed-environment` | 시스템 Python에 설치하지 말고 `.venv`의 Python으로 `pip install -r config/requirements.txt` 실행 |
| `ModuleNotFoundError` | `python -m pip --version`의 경로와 현재 Python이 같은 `.venv`인지 확인 |
| `pdfinfo` / `pdftoppm` 없음 | Ubuntu/WSL 안에 `poppler-utils` 설치하고 실행파일 확인 |
| `libreoffice` 없음 | Ubuntu/WSL 안에 `libreoffice-impress` 설치. Windows 프로그램 경로만 지정한 상태인지 확인 |
| PPTX PDF 변환 실패 | `reports/` 단계 로그 확인. 임시 경로 쓰기 권한·Impress 설치·LibreOffice 프로필 사용 충돌 확인 |
| 한글이 깨지거나 네모로 보임 | UTF-8 셸·파일 인코딩·한글 폰트를 각각 확인. JSON의 잘못된 원문 문자열과 렌더링 폰트 문제를 구분 |
| LH에서 HTML 오류 페이지를 받음 | 원문 브라우저 확인 후 동일 공고 HTML로 재실행. 잘못된 공고로 바꾸지 않음 |
| 주소 검증 실패 | `reports/unresolved-addresses.json` 확인. 임의의 시청 좌표 등으로 대체하지 않음 |
| 경쟁률이 "백엔드에 연결하지 못했습니다" | 정적 서버나 파일로 연 경우다. `./start_site.sh`로 실행. `--list`에서 그 사이트의 경쟁률 소스가 "미등록"이면 경쟁률 기능 이전 빌드이므로 새 실행으로 다시 빌드 |
| 경쟁률 "조회 불가"/"갱신 실패" | 상태 문구의 오류 확인. 공고 접수 전(표 없음), 정정공고로 주택군·공급호수 불일치, 네트워크 차단 등. 설정값을 응답에 맞춰 고치지 않음 |
| 서버 주소가 열리지 않음 | 터미널이 실행 중인지, 출력 폴더가 맞는지, 포트가 다른 서버와 충돌하는지 확인. WSL에서는 배포판·localhost 연결 확인 |
| 지도 배경만 빈 화면 | 인터넷·지도 타일 요청 확인. 목록 데이터 문제와 별개로 점검 |
| 다른 PC에서 파일 경로 오류 | 이전 PC의 절대 경로, 잘못 복사한 `.venv`, 환경 전용 `node_modules` 링크 확인 |

설정한 Python 패키지 버전을 남기려면 다음을 실행한다. 원본·로그를 삭제하거나 사이트 데이터를 바꾸지 않는다.

```bash
mkdir -p outputs/reports
python -m pip freeze > outputs/reports/python-environment.txt
```

이 문서의 설치 절차는 시스템을 실제로 재설치한 기록이 아니다. 현재 Ubuntu 환경의 도구 탐색·패키지 실행·데이터 검증을 확인했으며, Windows/WSL 설치와 Windows 브라우저 접속은 공식 절차 기반 안내다.
