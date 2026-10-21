---
name: lh-notice-map
description: Build an isolated LH rental-housing map from an LH notice URL, collecting non-HWP attachments and brochure popup addresses, importing the housing XLSX, linking PDF/image previews, and serving a 30-minute LH competition-rate backend (refresh button, ratio sort/filter). Use for similar LH notices, dataset replacement builds, or running/checking several notice sites at once; preserve all previous runs and sites.
---

# LH 공고 지도 빌더

LH 공고 URL에서 주택목록·첨부자료·홍보물 주소를 수집해 OpenStreetMap 지도 사이트를 만든다. 사이트에는 복수 선택 필터와 정렬, 미디어 미리보기, 30분 주기 청약 경쟁률이 있다. 같은 항목 안의 선택은 OR, 서로 다른 항목 사이는 AND다. 필터에 맞는 세대가 있는 건물만 지도에 남는다.

## 환경

작업공간 최상위의 두 스크립트를 쓴다. 둘 다 프로젝트 `.venv/`만 쓰고, pip·바이트코드 캐시는 `tmp/pip-cache/`, `tmp/pycache/`에 둔다. 공통 설정은 `scripts/project_env.sh`에 있다.

```bash
./setup_env.sh          # 최초 1회. 이미 갖춰진 단계(apt 패키지, 정상 .venv, 변경 없는 requirements)는 건너뜀
./setup_env.sh --no-system   # sudo 없이(apt 생략). 사이트 보기만 할 때
```

PDF 처리에는 Poppler, PPTX 처리에는 LibreOffice가 필요하다. 옵션 없는 `setup_env.sh`가 설치한다.

## 빌드

```bash
.venv/bin/python .agents/skills/lh-notice-map/scripts/build_notice.py 'LH_NOTICE_URL'
```

- 항상 새 `lh-runs/<UTC시각>-<panId>-<고유값>/`을 만든다. `--runs-dir`의 기본값은 실행 위치와 관계없이 프로젝트 루트의 `lh-runs/`이고, `LH_RUNS_DIR`로 바꿀 수 있다.
- 실행 폴더 구성: `docs/`(RUN.md·데이터 문서), `scripts/`, `config/`, `data/`, `site/dist/`, `backend/`, `reports/`, `tmp/`.
- 기본 명령은 다운로드부터 표준 검증, 독립 사이트 빌드까지 수행한다. Python 의존성이 없으면 실행 폴더의 `tmp/python-deps/`에 설치한다.
- 기존 폴더·데이터·사이트를 삭제하거나 덮어쓰지 않는다. 이전 실행과 작업공간의 활성 데이터 포인터(`public/`, `config/active-dataset.json`)를 바꾸지 않는다.
- 템플릿에는 현재 공고 데이터, `.git`, `.openai/hosting.json`, 사이트 ID가 들어 있지 않다.
- 성공한 실행이든 실패한 실행이든 보고서를 남긴다.

## 여러 공고 운용

공고 URL마다 빌드한 사이트는 `lh-runs/`에 계속 쌓이고, 같은 공고를 다시 빌드해도 새 폴더가 생긴다. 원본, 표준 데이터, 미리보기, 지오코딩 캐시, 사이트, 경쟁률 캐시(`tmp/competition/`)가 모두 실행 폴더 안에 있어 사이트끼리 상태를 공유하지 않는다.

빌드 폴더는 git에 커밋해 보관한다. 재생성할 수 있는 `reports/첨부파일.zip`과 실행별 `tmp/`는 `.gitignore`로 제외된다.

```bash
./start_site.sh --list       # 사이트별 폴더·경쟁률 소스 URL·실행 중 주소
./start_site.sh N            # N번 사이트 실행. 인자가 없으면 하나일 때 바로, 여러 개면 번호를 묻는다
./start_site.sh --all        # 실행 중이 아닌 모든 사이트를 백그라운드로 동시에 실행, 사이트별 URL 출력
./start_site.sh N --bg       # 한 사이트만 백그라운드로 실행(로그: tmp/logs/)
./start_site.sh N --stop     # 그 사이트만 중지
./start_site.sh --stop-all   # 목록의 모든 사이트 서버 중지
```

`start_site.sh`는 항상 전체 접속 URL(`http://localhost:…/`)을 한 줄로 출력한다. 같은 사이트가 이미 실행 중이면 재시작·중지·유지를 묻는다. 비대화형에서는 묻지 않고 주소만 출력하고 끝난다(`--restart`는 포트를 유지하며 재시작, `--stop`은 중지). 실행 여부는 `/proc`의 `backend/server.py --directory` 인자로 판별하므로 수동으로 띄운 서버도 찾는다.

## 청약 경쟁률 백엔드

사이트 폴더의 정적 파일과 `/api/competition`은 `backend/server.py`가 함께 제공한다. 이 서버는 Python 표준 라이브러리와 내장 SQLite만 쓰므로 Node.js가 필요 없다. 같은 규칙의 JS 구현 `backend/competition.mjs`는 호스팅 Worker용이며, 테스트가 두 파서의 결과를 같은 원문 픽스처로 대조한다. 브라우저는 LH를 직접 조회하지 않는다.

**소스 URL은 사이트 단위 설정이다.**
- 각 사이트 폴더(`public/`, `lh-runs/<실행>/site/dist/`)의 `competition-config.json`에 있는 `sourceUrl`이 소스다.
- 이 파일은 `activate`/`build`가 데이터셋의 `notice.sourceUrl`로 만들며, 공고 ID·원문 URL·총 세대수·주택군 목록을 담는다.
- 소스를 바꾸려면 데이터셋의 `notice.sourceUrl`을 고친 뒤 다시 activate한다. `competition-config.json`을 직접 편집하지 않는다.
- URL은 apply.lh.or.kr의 `selectWrtancInfo.do`여야 하고, `panId`가 데이터셋 ID와 같아야 한다.

백엔드는 이 URL을 30분마다 조회해 공급정보 표(`htyListTb08`)의 공급호수·모집인원·신청건수를 파싱한다.

- **저장 조건**: 응답의 `panId`, 합계 행, 주택군 집합, 총 공급호수가 설정과 정확히 일치할 때만 저장한다. 불일치는 정정공고나 데이터 교체 신호다. 값을 맞추지 말고 보고한다.
- **주택군 단위**: 같은 주택군의 여러 행은 합산하고, 그 주택군의 모든 건물에 같은 값을 연결한다. 세대별 경쟁률로 표시하지 않는다. 기준은 공급호수 기준(신청건수÷공급호수)과 모집인원 기준(신청건수÷모집인원) 중에서 고른다.
- **결측과 실패**: 미공개 값과 조회 실패 값은 null이며 0:1로 표시하지 않는다. 조회가 실패하면 마지막 정상 수치와 조회 시각을 유지하고 `stale-error`로 표시한다. 실패 후 재조회는 5분 간격으로 제한한다.
- **UI 패널**: 사이드바 `청약 경쟁률` 패널에 다음이 있다.
  - `경쟁률 새로고침` 버튼: `POST /api/competition/refresh`(동일 출처만 허용)로 30분 캐시를 무시하고 즉시 조회한다. 동시 요청은 하나의 조회를 공유한다.
  - `데이터 기준`: 마지막 정상 조회 시각, 경과 시간, 다음 자동 갱신 시각을 표시한다.
  - 카드와 지도 툴팁의 경쟁률에도 기준 시각이 붙는다.
- **정렬·필터**: 정렬에 `경쟁률순`·`신청건수순`이 있고, 미공개 값은 방향과 관계없이 맨 뒤다. 복수 선택 필터에 경쟁률 구간(1:1 미만, 1~5, 5~10, 10~20, 20 이상, 미공개)이 있다.
- **호스팅**: 호스팅(Workers)에는 타이머가 없다. 그래서 `GET /api/competition`이 30분이 지났을 때(실패 후라면 5분) 지연 갱신한다. 저장소는 같은 스키마의 D1 `competition_cache` 테이블이다.

## URL·접근 제약 처리

- `panId`가 없는 URL은 공고를 식별하지 못한다. 스크립트의 `needs_browser` 결과를 확인하고, 사용자가 브라우저로 연 상세 공고에서 제목, 실제 ID, 주택목록 파일 ID를 확인한다. 이전/최신 공고로 추측하지 않는다.
- 직접 접근이 막히면 브라우저 도구로 같은 공고를 연다. 실제 페이지 HTML을 저장한 후 `--html /path/notice.html --notice-id VERIFIED_ID`로 새 실행을 한다. 사용자에게 브라우저 대신 파일 업로드부터 요구하지 않는다.
- 세션에 보이는 공고를 식별할 수 없을 때만 구체적 공고 ID나 제목을 질문한다. 인증·CAPTCHA 제한을 우회하지 않는다.
- 여러 주택목록, 불명확한 헤더, 미확정 좌표는 임의로 선택하지 않는다. 보고서를 읽고 확인한 설정/좌표를 입력하여 새 실행을 한다.

## 확인과 전달

1. `reports/run.json`의 `status: complete`와 검증 개수를 확인한다. 원본 미기재는 null로 보존한다. HWP/HWPX는 받지 않는다. 한글 파일명은 UTF-8로 보존한다.
2. `config/notice.json`의 기준 XLSX ID·시트·헤더·열 매핑과 공고일을 원문과 대조한다. 자동 감지가 안 되면 `--config`를 쓴다. 설정 예시와 관계 규약은 [데이터 교체 가이드](references/DATA_GUIDE.md), [미디어 표준](references/DATA_STANDARD.md)에서 필요한 부분만 읽는다. 두 문서는 빌드 때 실행 폴더의 `docs/`로도 복사된다.
3. `./start_site.sh N`으로 새 실행을 연다. 서버 시작 메시지의 `경쟁률 소스:` URL이 이 공고인지 먼저 확인한다. 이어서 다음을 확인한다.
   - 제목, 세대·주소 수
   - 복수 선택 필터에 따른 목록/핀 동기화, 표 정렬
   - 경쟁률 표시·정렬·필터, `경쟁률 새로고침`, `데이터 기준` 시각
   - PDF 페이지·원본 이미지 열기

   `curl -s <URL>api/competition`의 `status: ok`와 `data.totals`가 원문 합계 행과 같은지도 대조한다. 공고 접수 전이라 표가 없으면 `unavailable`이 정상이며, 지도는 그대로 동작한다.
4. 다운로드 원본과 정리 XLSX는 `data/notices/lh_ID/`에, 전달 ZIP은 `reports/첨부파일.zip`(git 제외)에 있다. 보고서는 미기재와 미등록 홍보물을 그대로 드러내야 한다.
5. 게시는 사이트 게시가 요청됐거나 Sites 워크플로를 적용하는 경우에만 한다.
   - **새** Sites 프로젝트로 게시하고, 새 식별정보는 실행 폴더에 저장한다. 현재 프로젝트나 이전 실행의 ID를 재사용하지 않는다.
   - 기존 사이트 갱신은 사용자가 그 사이트를 명시해 요청한 경우에만 별도로 한다.
   - 로컬 빌드를 배포 성공이라고 말하지 않는다.

## 재사용·재시도

- `--from-bundle DIR`은 URL·ID가 일치하는 표준 패키지로 독립 사이트를 만든다.
- `--reuse-downloads DIR`, `--reuse-assets DIR`, `--geocodes FILE`은 검토를 마친 기존 자료를 **읽기 전용 입력**으로 복사한다.
- 기본 실행은 자료를 새로 수집한다. 원본 해시와 표준 참조·페이지 수를 다시 검증하므로 다른 공고의 자산이 섞이지 않는다.
- 불완전한 자료로 완료 상태를 만들지 않는다.
