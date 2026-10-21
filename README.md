# 든든전세 지도

LH 공고의 주택목록·홍보물을 지도에서 보고, 청약 경쟁률을 30분마다 갱신해 함께 보여 주는 웹 사이트입니다. 작업공간 사이트(`public/`)는 2026.09.30 경기남부 든든전세 정정공고이고, 다른 공고는 스킬로 `lh-runs/`에 빌드해 함께 운용합니다.

## 실행

Windows·Ubuntu의 설치, 가상환경, Poppler·LibreOffice·한글 폰트, 실행·검증 및 문제 해결은 [환경설정 가이드](docs/ENV_SETUP.md)를 참고하세요. Windows 전체 빌드는 WSL2 + Ubuntu 기준입니다.

프로젝트 폴더에서 두 명령을 실행합니다.

```bash
./setup_env.sh    # 최초 1회: 시스템 도구(필요할 때만 sudo apt) → .venv → 패키지 → 설치 확인 → 테스트
./start_site.sh   # 사이트 + 경쟁률 백엔드 실행. 사이트가 여러 개면 번호로 선택, 모두 실행은 --all
```

브라우저에서 출력된 주소(기본 `http://localhost:8765/`)를 엽니다. Python은 프로젝트의 `.venv/`만 사용하며, pip 다운로드 캐시와 `__pycache__`는 `tmp/pip-cache/`, `tmp/pycache/`에 둡니다. Node.js와 API 키는 필요하지 않습니다. 지도 배경과 경쟁률 조회에는 인터넷 연결이 필요합니다. `setup_env.sh`는 이미 갖춰진 단계를 건너뛰므로 여러 번 실행해도 됩니다. sudo 권한이 없거나 사이트 보기만 필요하면 `--no-system`으로 apt 단계를 생략합니다.

백엔드(`backend/server.py`, Python 표준 라이브러리)는 선택한 사이트 폴더를 제공하면서, 그 폴더의 `competition-config.json`에 적힌 `sourceUrl`(LH 원문 공고)을 소스로 신청 현황(공급호수·모집인원·신청건수)을 30분마다 조회합니다. 소스 URL은 사이트마다 다르며 데이터셋의 `notice.sourceUrl`에서 `activate`/`build` 때 생성되므로 직접 편집하지 않습니다. 캐시는 작업공간 사이트는 `data/runtime/`, 실행 폴더 사이트는 그 실행의 `tmp/competition/`에 저장합니다. 사이드바 `청약 경쟁률` 패널의 `경쟁률 새로고침` 버튼은 즉시 다시 조회하고, 패널의 `데이터 기준`에 마지막 조회 시각·경과 시간·다음 자동 갱신 시각을 표시합니다. 경쟁률은 주택군 단위이며 공급호수 기준과 모집인원 기준을 고를 수 있고, 경쟁률순·신청건수순 정렬과 경쟁률 구간 필터를 제공합니다. 조회 실패 시 마지막 정상 수치와 조회 시각을 유지합니다. `./start_site.sh`는 항상 복사해서 쓸 수 있는 전체 접속 주소를 출력합니다. 같은 사이트가 이미 실행 중이면 재시작·중지·그대로 두기를 묻습니다(`--restart`, `--stop`). `./start_site.sh --list`는 사이트별 폴더, 경쟁률 소스 URL, 실행 중인 주소를 보여 줍니다.

공고 URL로 빌드한 사이트는 `lh-runs/`에 공고·빌드별 폴더로 계속 쌓이며 서로 덮어쓰지 않습니다. 빌드 폴더는 git에 커밋하며, 재생성할 수 있는 전달 ZIP(`reports/첨부파일.zip`)과 실행별 `tmp/`만 제외합니다. `./start_site.sh --all`로 모든 사이트를 동시에 띄우고(사이트별 URL 출력), `./start_site.sh --stop-all`로 모두 중지합니다. 경쟁률 기능 추가 전에 만든 실행 폴더는 소스 URL이 없어 지도만 동작합니다.

## 데이터 기준

- 공고 식별값: `2015122300020927`
- 정정 주택목록 엑셀: `69044664`
- 원본 344세대, 56개 주소 문자열, 38개 주택군의 17개 열을 보존합니다.
- 실사용면적이 비어 있는 4세대는 빈값으로 유지합니다.
- 원문 주소별 지도 마커를 만들고, 같은 위치는 묶어서 선택합니다. 임의 좌표 이동은 하지 않습니다.
- 미디어 연결은 주소 일치, 같은 위치, 같은 주택군의 세 단계로 표시합니다. 공통 홍보물을 다른 건물의 전용 자료로 표시하지 않습니다.
- PDF와 PPTX의 모든 페이지를 WebP 이미지로 변환했습니다. XLSX는 원본 다운로드를 제공합니다.

## 새 공고 교체

표준 패키지를 준비하면 화면 코드를 수정하지 않고 교체할 수 있습니다. [데이터 교체 가이드](.agents/skills/lh-notice-map/references/DATA_GUIDE.md), [PDF·이미지 관계 표준](.agents/skills/lh-notice-map/references/DATA_STANDARD.md), [JSON 스키마](data/schema/notice-dataset.schema.json)를 참고하세요.

```bash
python scripts/dataset.py validate --dataset data/datasets/공고ID/dataset.json --asset-root data/datasets/공고ID
python scripts/dataset.py activate --dataset data/datasets/공고ID/dataset.json --asset-root data/datasets/공고ID
```

활성화 후 브라우저를 새로고침합니다. 실제 호스팅 사이트는 `scripts/build_hosted.mjs`로 `dist/`를 다시 만들어 게시해야 합니다. `public/data.js`는 생성물이므로 직접 수정하지 않습니다. 새 XLSX는 `scripts/import_xlsx.py`와 `config/lh-current.json`의 시트·열 매핑으로 표준 패키지에 넣습니다.

기존 수집·변환 도구도 남겨 두었습니다. `scripts/collect_lh.py`는 `LH_PAN_ID`와 `LH_NOTICE_HTML`을 받아 첨부를 수집합니다. `scripts/prepare_site_assets.py`에는 Pillow, Poppler, LibreOffice가 필요합니다. `scripts/geocode_addresses.py`는 한 번 수집한 주소 검색 응답을 `tmp/`에 저장해 재사용하며 페이지 이용 중에는 주소 검색 API를 호출하지 않습니다. 중간 산출물은 `scripts/dataset.py import-current`로 변환합니다. `scripts/build_data.py`는 표준 활성화 명령의 호환 진입점입니다.

`media-sync-audit.json`은 원본 세대 정보 보존, 좌표와 미디어 연결, 파일 경로 검증 결과입니다. `source-data.json`에는 원본 엑셀의 각 셀 값과 행 번호가 있습니다.

주요 기능 설계와 구현 체크리스트, 원본 대조 검증 결과는 [design.md](docs/design.md)에 기록합니다. 지역·보증금·면적·방수·유형·승강기 필터는 각각 복수 선택할 수 있습니다. 같은 항목 안에서는 OR, 서로 다른 항목 사이에서는 AND로 결합하며, 일치하는 세대가 있는 건물만 목록과 지도에 함께 표시합니다.

## 지도와 라이브러리

지도 배경: [OpenStreetMap](https://www.openstreetmap.org/copyright). 지도 UI: [Leaflet](https://leafletjs.com/), [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster). 좌표 확인: 카카오맵 공개 주소 검색. 공고와 첨부파일의 출처는 화면의 LH 원문 링크와 원본 다운로드에 표시합니다.

검색·정렬·필터는 브라우저에서 실행합니다. 서버는 정적 파일과 경쟁률 API만 제공하며 로그인은 없습니다. 저장한 건물은 해당 브라우저의 로컬 저장소에 보관됩니다.

## 폴더 구분

| 폴더 | 보관 내용 |
|---|---|
| `setup_env.sh`, `start_site.sh` | 환경 구성, 사이트 실행·중지 진입점(공통 설정 `scripts/project_env.sh`) |
| `docs/` | 설계 기록(`design.md`), 환경설정(`ENV_SETUP.md`), 스킬 사용 가이드(`SKILL_GUIDE.md`) |
| `.agents/skills/lh-notice-map/` | 스킬 실행기·템플릿·데이터 표준과 교체 가이드(`references/`) |
| `.claude/skills/lh-notice-map/` | Claude Code용 스킬 절차 |
| `scripts/` | Python 수집·변환·검증 도구, 실행 중 서버 탐지, 호스팅 빌드 |
| `config/` | 공고별 열 매핑, 활성 데이터 상태 |
| `data/notices/` | 공고별 원본 첨부파일, 홍보물, 수집 명세, 정리 XLSX |
| `data/datasets/` | 표준 JSON과 원본·페이지·썸네일 자산 |
| `data/intermediate/` | 공고별 원본 셀 추출·검증 좌표·연결 감사 자료 |
| `data/schema/` | 데이터 JSON 스키마 |
| `public/` | 브라우저에 제공하는 지도 앱과 활성 데이터 스냅샷 |
| `backend/` | 경쟁률 백엔드(`server.py`·`competition.py` 로컬 서버, `competition.mjs`·`site/` 호스팅 Worker) |
| `dist/` | `scripts/build_hosted.mjs`가 만드는 호스팅 빌드 출력(무시됨) |
| `lh-runs/` | 스킬로 빌드한 공고별 독립 사이트(커밋 대상, 전달 ZIP·`tmp/` 제외) |
| `tests/` | 검증 테스트와 독립 예제 데이터 |
| `outputs/` | 사용자 전달 ZIP과 배포 패키지 |
| `tmp/` | 재생성 가능한 캐시(pip·pycache), 서버 로그, 검토용 빌드 |
| `.venv/` | `setup_env.sh`가 만드는 프로젝트 전용 Python 환경(무시됨) |

`.git`과 `.openai/hosting.json`은 작업공간 최상위에서 기존 사이트의 이력을 유지합니다. 새 스킬 실행은 이 식별정보를 복사하지 않고 별도 실행 폴더를 만듭니다.

## 프로젝트 전용 스킬

Codex 스킬은 [`.agents/skills/lh-notice-map/`](.agents/skills/lh-notice-map/SKILL.md), Claude Code 스킬은 [`.claude/skills/lh-notice-map/`](.claude/skills/lh-notice-map/SKILL.md)에 있습니다. 공용 홈 경로에는 설치하지 않습니다. 사용법과 폴더 보존 원칙은 [스킬 실행 가이드](docs/SKILL_GUIDE.md)에 있습니다.

```bash
.venv/bin/python scripts/build_notice.py 'LH_공고_URL'   # 기본 출력: 프로젝트 루트의 lh-runs/
./start_site.sh --all                                  # 빌드된 모든 사이트 실행
```

실행마다 새 폴더가 생깁니다. 기존 데이터 교체·삭제나 기존 사이트 게시를 자동 수행하지 않습니다.
