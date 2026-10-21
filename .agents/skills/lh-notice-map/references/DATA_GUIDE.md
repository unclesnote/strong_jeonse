# 공고 데이터 준비 가이드

새 공고는 항상 스킬(`build_notice.py`)이 `lh-runs/`에 **사이트를 하나 더 추가**해서 반영한다. 기존 사이트는 바꾸지 않는다. 대부분의 공고는 URL만 주면 끝난다. 이 문서는 자동 처리가 안 될 때 스킬에 넘길 입력을 준비하는 방법을 다룬다. 예를 들어 주택목록 XLSX를 자동으로 감지하지 못했거나, 이미 만든 표준 패키지가 있거나, 예전 형식의 자료를 옮겨야 할 때다.

표준 정의는 [`DATA_STANDARD.md`](DATA_STANDARD.md), 설계 기록은 작업공간의 `docs/design.md`를 참고한다. 명령은 작업공간 최상위에서 실행한다. 환경은 `./setup_env.sh`로 준비한다. 아래 `python`은 작업공간의 `.venv/bin/python`이다(`source .venv/bin/activate` 후 `python`).

## 1. 입력 방식 선택

| 가진 자료 | 사이트 추가 방법 |
|---|---|
| LH 공고 URL만 | `python scripts/build_notice.py 'URL'` (수집부터 자동) |
| URL + 자동 감지가 안 되는 주택목록 XLSX | 2절의 설정 파일을 만들어 `--config 설정.json` 추가 |
| 표준 `dataset.json`과 `assets/` 폴더 | 3절의 검증 후 `--from-bundle 폴더` |
| 이전 스크립트가 만든 `source-data.json`·좌표·첨부 명세 | 4절에서 표준 패키지로 변환한 뒤 `--from-bundle` |

어느 방식이든 결과는 `lh-runs/<시각>-<panId>-<고유값>/`의 새 사이트다. 실행은 `./start_site.sh`로 한다. XLSX만으로 홍보물 연결과 좌표를 추측하지 않는다. 새 주소의 좌표와 실제 파일·미리보기 준비는 필요하다.

## 2. 설정 파일로 주택목록 XLSX 지정(`--config`)

스킬은 주택목록 XLSX를 자동으로 고르고 시트·헤더·열을 감지한다. 주택목록이 여러 개이거나 헤더가 불명확하면 추측하지 않고 멈춘다. 그때 설정 파일을 만들어 `--config`로 넘긴다.

```bash
python scripts/build_notice.py 'URL' --config config/my-notice.json
```

작업공간의 `config/lh-current.json`이 완성된 예시다. 이 파일의 `notice`, `spreadsheet`, 선택적 `groupAliases`만 새 공고에 맞게 고친다. `paths`는 스킬이 실행 폴더의 경로로 자동 설정하므로 적지 않아도 된다.

1. `notice`: 새 공고 ID·원문 제목·날짜·URL·화면 제목·지역·배지·공급기관. `id`와 `sourceUrl`의 `panId`는 URL과 같아야 한다. `sourceUrl`은 경쟁률 백엔드의 소스가 된다.
2. `spreadsheet.fileId`: 기준 주택목록 XLSX의 첨부 파일 ID
3. `spreadsheet.sheetName`, `headerRow`, `dataStartRow`, `columns`

### 엑셀 열 위치가 달라졌을 때

`columns`는 화면의 표준 필드와 원본 열을 연결한다. 다음처럼 열 문자 또는 헤더 이름을 쓸 수 있다.

```json
{
  "columns": {
    "id": "A",
    "group": {"header": "모집단위(주택군)"},
    "address": {"header": "주소"},
    "deposit": {"header": "임대보증금"},
    "area": {"header": "실사용면적"},
    "expandedArea": null
  }
}
```

이 예시는 매핑 일부다. 실행에는 `lh-current.json`의 전체 설정을 사용한다. 헤더의 공백·줄바꿈은 비교할 때 정리한다. 같은 이름의 열이 여러 개이면 어느 열인지 추측하지 않고 중단하므로 열 문자를 지정한다. 파일에 없는 선택 항목은 `null`로 매핑한다. 순번·주택군·주소는 필수다.

방수·보증금·면적에는 원본 숫자 또는 빈값이 있어야 한다. ‘2억’ 같은 문자열을 원으로 추측 변환하지 않는다. 승강기 문구가 달라지면 `elevatorYesValues`·`elevatorNoValues`를 설정한다. 원본 빈값은 미기재로 유지한다.

순번은 `spreadsheet.idType`으로 `auto`(기본), `string`, `integer`를 지정할 수 있다. `auto`에서도 `001`처럼 앞에 0이 있는 값은 문자열로 유지한다. 원본에서 `001`과 `1`이 구분되는 식별자라면 임의로 같은 순번으로 합치지 않는다.

XLSX와 수집 명세의 파일 ID·파일명을 대조한다. 다른 공고의 엑셀과 홍보물을 실수로 결합하면 가져오기를 중단한다. 공급자료의 주택군 명칭과 엑셀 명칭이 다른 경우에만 확인한 `groupAliases`를 명시한다. `rawFields`는 원본 값을 계속 보존한다.

추출 결과는 실행 폴더의 `data/intermediate/<ID>/source-data.json`에서 세대수·주소·원본 행·미기재 값을 확인한다. 설정이 틀렸으면 고쳐서 새 실행으로 다시 추가한다. 실패한 실행 폴더는 `./delete_site.sh`로 지울 수 있다.

## 3. 표준 패키지로 추가(`--from-bundle`)

다음 구조의 표준 패키지가 있으면 수집 없이 사이트를 추가한다.

```text
data/datasets/<공고ID>/
  dataset.json
  assets/files/...
  assets/previews/...
```

먼저 검증한다. 이 명령은 아무것도 쓰지 않는다.

```bash
python scripts/dataset.py validate \
  --dataset data/datasets/<공고ID>/dataset.json \
  --asset-root data/datasets/<공고ID>
```

`--asset-root`는 그 아래에 `assets/`가 있는 폴더다. `assets/` 자체를 지정하지 않는다. 통과하면 사이트를 추가한다. URL의 `panId`와 패키지의 공고 ID가 같아야 한다.

```bash
python scripts/build_notice.py 'URL' --from-bundle data/datasets/<공고ID>
```

## 4. 이전 수집 형식에서 변환

기존 파이프라인의 자료가 있으면 먼저 표준 패키지로 바꾼 뒤 3절로 추가한다.

```bash
python scripts/dataset.py import-current \
  --notice-id <공고ID> \
  --source path/to/source-data.json \
  --geocodes path/to/geocodes.json \
  --attachments path/to/assets/attachments.json \
  --asset-root path/to/bundle-root \
  --manifest path/to/manifest.json \
  --notice-config path/to/notice-metadata.json \
  --output data/datasets/<공고ID>/dataset.json
```

`notice-metadata.json`은 `lh-current.json`의 `notice` 객체만 담은 파일이다. `--notice-id`와 그 객체의 `id`는 같아야 한다. 변환기는 원본 셀값·행 번호, 파일 해시, 홍보물 연결 근거를 보존한다. 이 명령은 `--output` 파일만 쓴다.

## 5. PDF·이미지·평면도 연결하기

1. 실제 원본 파일을 `assets/files/`에 둔다.
2. PDF는 모든 페이지, PPTX는 모든 슬라이드를 이미지로 변환한다. 일반 이미지는 미리보기 1페이지다.
3. `media`에 원본 해시·크기·미리보기 페이지·부모 미디어 ID·썸네일을 등록한다.
4. `relations`로 공고·주택군·건물·세대 중 실제 대상을 지정한다.
5. 건물 전용으로 확정할 수 없는 주택군 공통 자료는 `match: "group"`으로 표시한다.
6. 세대 전용 평면도는 `targetType: "unit"`으로 연결한다. 다른 세대만 검색되면 해당 전용 자료는 표시하지 않는다.

PDF를 새 파일로 바꾸었다면 원본 `sha256`·`size`, 모든 페이지와 썸네일도 새로 만든다. 파일명만 바꾸고 기존 이미지 미리보기를 유지하지 않는다.

## 6. 추가 전후 확인 항목

- [ ] 공고 ID·제목·날짜·원문 URL이 새 공고와 일치
- [ ] 기준 XLSX·정정 여부·파일 ID가 맞음
- [ ] 모든 원본 세대 순번과 17개 표준 항목이 보존됨
- [ ] 미기재 면적·승강기 등을 0·없음으로 임의 치환하지 않음
- [ ] 원문 주소마다 검증 좌표와 출처가 있음
- [ ] 모든 PDF 페이지와 이미지 부모 관계가 맞음
- [ ] 주택군 공통 자료와 특정 세대 자료의 관계가 구분됨
- [ ] `validate` 통과, 새 실행의 `reports/run.json`이 `complete`
- [ ] `./start_site.sh`로 연 새 사이트의 제목·세대수·주소수·필터·홍보물 미리보기 확인
- [ ] 지역·방수 등을 복수 선택했을 때 검색된 건물만 지도에 표시됨
- [ ] `./start_site.sh --list`의 경쟁률 소스 URL이 새 공고이고, 경쟁률 패널이 `정상 조회`(접수 전이면 `조회 불가`)
- [ ] 기존 사이트들은 그대로 남아 있음

## 7. 오류

| 오류 | 확인할 내용 |
|---|---|
| 스키마 버전 불일치 | 지원 버전은 1.0.0. 파일의 버전 숫자만 고쳐 호환되는 척하지 말고 형식을 변환한다. |
| 없는 ID를 참조 | `buildingId`, `groupId`, `mediaId`, 관계 대상의 오타·누락 확인 |
| 주소 일치·동일 위치 검증 실패 | 연결 근거와 원문 주소 확인. 임의 좌표를 넣어 통과시키지 않는다. |
| 원본 해시·크기 불일치 | 현재 파일의 실제 내용과 명세가 다름. 원본과 파생 이미지를 함께 재생성 |
| 파일 없음·잘못된 경로 | `asset-root`와 `assets/...` 상대 경로 확인 |
| 페이지 부모·번호 오류 | 모든 파생 이미지의 부모가 실제 원본 ID인지, 1부터 연속인지 확인 |
| XLSX 열·시트 오류 | 시트 이름·헤더 행·데이터 시작 행·열 매핑 확인 |
| 수식 캐시 없음 | 원본을 계산 가능한 스프레드시트 앱에서 계산·저장한 뒤 다시 가져오기 |
| `Site already has data` | 이미 데이터가 있는 사이트 폴더에 쓰려 했다. 사이트는 바꾸지 않고 항상 새로 추가한다. 스킬로 새 실행을 만든다. |

검증이나 빌드가 실패한 실행도 폴더와 보고서를 남긴다. 반쯤 만든 사이트는 데이터 파일이 없으므로 화면에 공고가 나오지 않는다. 원인을 고쳐 새 실행으로 다시 추가한다. 필요 없는 실행은 `./delete_site.sh`로 지운다.

`dataset.py build`로 사이트 없이 데이터·미디어 출력만 검토할 수도 있다. 출력 폴더가 이미 있으면 거부한다.

```bash
python scripts/dataset.py build \
  --dataset data/datasets/<공고ID>/dataset.json \
  --asset-root data/datasets/<공고ID> \
  --output tmp/review-build
```
