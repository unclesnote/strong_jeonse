---
name: lh-notice-map
description: Build an isolated LH rental-housing map from an LH notice URL, collecting non-HWP attachments and brochure popup addresses, importing the housing XLSX, and linking PDF/image previews. Use for similar LH notices or dataset replacement builds; preserve all previous runs and sites.
---

# LH 공고 지도 빌더

LH 공고 URL에서 주택목록·첨부자료·홍보물 주소를 수집하고, 복수 선택 필터와 정렬 및 미디어 미리보기가 있는 OpenStreetMap 지도를 만든다. 같은 항목의 선택은 OR, 서로 다른 항목은 AND다. 필터에 맞는 세대가 있는 건물만 지도에 남는다.

## 실행

이 스킬 디렉터리의 `scripts/build_notice.py`를 실행한다.

```bash
python .agents/skills/lh-notice-map/scripts/build_notice.py 'LH_NOTICE_URL' --runs-dir /workspace/lh-runs
```

항상 새 `시각-panId-고유값/`을 만든다. 그 안의 `docs/`, `scripts/`, `config/`, `data/`, `site/`, `reports/`, `tmp/`를 사용한다. 기본 명령은 다운로드부터 표준 검증·독립 정적 빌드까지 수행한다. Python 의존성이 없으면 실행 폴더의 `tmp/python-deps/`에 설치한다. PDF는 Poppler, PPTX는 LibreOffice가 필요하다.

기존 폴더·데이터·사이트를 삭제하거나 덮어쓰지 않는다. 이전 실행과 현재 작업공간의 활성 데이터 포인터를 바꾸지 않는다. 템플릿은 현재 공고 데이터, `.git`, `.openai/hosting.json`과 사이트 ID를 포함하지 않는다. 성공·실패한 실행 모두 보고서를 남긴다.

## URL·접근 제약 처리

- `panId`가 없는 URL은 공고를 식별하지 못한다. 스크립트의 `needs_browser` 결과를 확인하고 브라우저로 사용자가 연 상세 공고의 제목, 실제 ID, 주택목록 파일 ID를 확인한다. 이전/최신 공고로 추측하지 않는다.
- 직접 접근이 막히면 브라우저 도구로 같은 공고를 연다. 실제 페이지 HTML을 저장한 후 `--html /path/notice.html --notice-id VERIFIED_ID`로 새 실행을 한다. 사용자에게 브라우저 대신 파일 업로드부터 요구하지 않는다.
- 세션에 보이는 공고를 식별할 수 없을 때만 구체적 공고 ID나 제목을 질문한다. 인증·CAPTCHA 제한을 우회하지 않는다.
- 여러 주택목록, 불명확한 헤더, 미확정 좌표는 임의로 선택하지 않는다. 보고서를 읽고 확인한 설정/좌표를 입력하여 새 실행을 한다.

## 확인과 전달

1. `reports/run.json`의 `status: complete`와 검증 개수를 확인한다. 원본 미기재는 null로 보존한다. HWP/HWPX는 받지 않는다. 한글 파일명은 UTF-8로 보존한다.
2. `config/notice.json`에서 기준 XLSX ID·시트·헤더·열 매핑과 공고일을 원문과 대조한다. 자동 감지 불가 시 `--config`를 사용한다. 설정 예시와 관계 규약은 [데이터 교체 가이드](references/DATA_GUIDE.md), [미디어 표준](references/DATA_STANDARD.md)을 필요한 부분만 읽는다.
3. 브라우저에서 `site/dist`를 열어 제목, 세대·주소 수, 복수 선택 필터에 따른 목록/핀 동기화, 표 정렬, PDF 페이지·원본 이미지 열기를 확인한다. 서빙 명령은 생성된 `docs/RUN.md`에 있다.
4. 다운로드 원본과 정리 XLSX는 `data/notices/lh_ID/`, 전달 ZIP은 `reports/첨부파일.zip`이다. 보고서는 미기재와 미등록 홍보물을 그대로 드러내야 한다.
5. 사이트 게시가 요청되었거나 Sites 워크플로를 적용하는 경우, **새** Sites 프로젝트로 게시하고 실행 폴더에 새 식별정보를 저장한다. 현재 프로젝트나 이전 실행의 ID를 재사용하지 않는다. 기존 사이트 갱신은 사용자가 그 사이트를 명시해 요청한 경우에만 별도로 수행한다. 로컬 빌드를 배포 성공이라고 말하지 않는다.

## 재사용·재시도

`--from-bundle DIR`은 URL과 ID가 일치하는 표준 패키지로 독립 사이트를 만든다. `--reuse-downloads DIR`, `--reuse-assets DIR`, `--geocodes FILE`은 검토한 기존 자료를 **읽기 전용 입력**으로 복사한다. 기본 실행은 새로 수집한다. 원본 해시와 표준 참조·페이지 수를 재검증하므로 다른 공고의 자산을 섞지 않는다. 불완전한 자료로 완료 상태를 만들지 않는다.
