# LH URL 지도 빌드 스킬

스킬은 이 프로젝트의 [`.agents/skills/lh-notice-map/SKILL.md`](../.agents/skills/lh-notice-map/SKILL.md)에 있습니다. 프로젝트 전용 스킬 검색 위치는 `.agents/skills/`입니다. 공용 폴더에 설치하지 않습니다. [공식 문서](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

Codex에서 `$lh-notice-map 이 공고 URL로 새 지도 사이트를 만들어줘`로 요청합니다. 목록에 바로 보이지 않으면 프로젝트를 다시 열거나 위 SKILL.md 경로를 직접 지정합니다.

명령으로 실행할 때는 작업공간 최상위에서 다음을 사용합니다.

```bash
python scripts/build_notice.py 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=실제공고ID' --runs-dir lh-runs
```

`panId` 없는 URL만으로는 어떤 공고인지 식별할 수 없습니다. 이때는 `needs_browser` 보고서를 남기고 멈춥니다. 스킬을 수행하는 에이전트가 브라우저의 실제 공고와 파일 ID를 확인한 후 HTML을 저장하여 `--html 확인한공고.html --notice-id 실제ID`로 새 실행을 이어갑니다. 앞선 공고나 최신 공고를 임의 선택하지 않습니다.

## 실행마다 만드는 폴더

```text
lh-runs/<UTC시각>-<공고ID>-<고유값>/
├── docs/       # 데이터 관계 규약, 실행 안내
├── scripts/    # 해당 빌드에 사용한 수집·변환 도구
├── config/     # 확정 XLSX 매핑·공고 메타데이터·검증 상태
├── data/
│   ├── notices/lh_<ID>/  # 공고 첨부·건물별 홍보물·정리 XLSX
│   ├── intermediate/<ID>/ # 원본 셀·검증 좌표
│   ├── datasets/<ID>/   # 표준 JSON과 원본·페이지·썸네일
│   └── schema/          # 데이터 스키마
├── site/dist/  # 별도 지도 사이트
├── reports/    # run.json·단계별 로그·전달 ZIP
└── tmp/        # 의존성·변환 캐시
```

폴더명에 고유값을 포함하여 같은 공고를 연속 실행해도 기존 결과를 덮어쓰지 않습니다. 실패한 실행도 지우지 않습니다. 기존 프로젝트의 활성 상태나 사이트 ID를 복사하지 않습니다. 새 사이트를 게시할 때 새 Sites 프로젝트로 등록합니다. 현재 사이트 갱신은 해당 사이트를 명시한 별도 요청으로 수행합니다.

## 입력과 검증

기본 실행은 첨부파일과 홍보물 팝업 주소를 수집하고 HWP/HWPX를 제외합니다. 주택목록 XLSX를 확정하여 시트·열을 감지하고, PDF/PPTX 전체 페이지와 이미지 미리보기를 생성합니다. 주소별 좌표를 검증한 후 표준 JSON을 검증하고 새 `site/dist`에 빌드합니다.

주택목록이 여러 개이거나 헤더가 불명확하면 추측하지 않습니다. [현재 설정 예시](../config/lh-current.json)를 참고해 확인한 `notice`, `spreadsheet`, 선택적 `groupAliases`를 JSON으로 준비하고 `--config 설정.json`을 지정합니다. `paths`는 실행 폴더의 새 경로로 자동 설정합니다. 공고 날짜도 원문과 대조합니다.

필터는 한 항목 안에서 OR, 항목 사이에서 AND를 적용하며 같은 세대가 모든 조건을 충족해야 합니다. 해당 세대가 있는 건물만 지도에 표시합니다. 세대 전용 미디어는 제외된 세대와 함께 숨깁니다. 원본 미기재는 0이나 ‘없음’으로 바꾸지 않습니다.

`reports/run.json`의 `status: complete`와 `config/validation-audit.json`을 확인합니다. 정리 XLSX는 `data/notices/lh_<ID>/첨부파일정리.xlsx`, ZIP은 `reports/첨부파일.zip`입니다. 로컬 결과가 완료되었다고 호스팅 게시도 완료된 것은 아닙니다.

## 검증한 자료 재사용

- `--from-bundle 패키지폴더`: 완성된 표준 패키지로 독립 사이트를 새로 만듭니다.
- `--reuse-downloads 원본폴더`: 같은 공고의 기존 원본을 복사합니다.
- `--reuse-assets assets폴더`: 같은 원본에서 생성한 미리보기를 복사합니다.
- `--geocodes 좌표.json`: 확인한 좌표 명세를 복사합니다.

모두 읽기 전용 입력으로 사용하며 공고 ID·파일 해시·관계·페이지 수를 다시 검증합니다. 실패한 실행을 같은 폴더에서 덮어 재시도하지 않고 새 실행으로 남깁니다. 미확정 주소는 `reports/unresolved-addresses.json`에서 확인하며 임의 좌표로 대체하지 않습니다.
