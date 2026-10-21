# 새 공고 데이터 교체 가이드

지도 HTML·CSS·JavaScript를 수정하지 않고 공고를 교체하는 방법이다. 모든 명령은 `sites/jeonse-map` 폴더에서 실행한다. 표준 정의는 [`DATA_STANDARD.md`](DATA_STANDARD.md), 현재 구현과 TODO는 [`design.md`](design.md)를 참고한다.

실행 환경은 Python 3.10 이상과 `jsonschema` 4.x, Poppler의 `pdfinfo`가 필요하다. 이 작업 환경에는 설치되어 있다. 새 환경에서는 Python 패키지를 `python -m pip install "jsonschema>=4.10,<5"`로 설치하고, 운영체제의 Poppler 패키지를 설치한다. 미리보기를 새로 변환할 때에는 `pdftoppm`, Pillow, PPTX용 LibreOffice도 필요하다. 검증은 PDF 원본 페이지 수를 확인할 도구가 없으면 통과 처리하지 않는다.

## 1. 입력 방식 선택

| 가진 자료 | 사용할 방법 |
|---|---|
| 표준 `dataset.json`과 `assets/` 폴더 | 2절의 검증·활성화만 실행 |
| 새 LH 주택목록 XLSX와 수집·좌표·미리보기 명세 | 3절의 설정 기반 가져오기 후 활성화 |
| 이전 스크립트가 만든 `source-data.json`·좌표·첨부 명세 | 4절의 이전 형식 변환 후 활성화 |

‘데이터만 교체’는 공고 내용과 미디어 연결을 표준 파일로 제공하면 화면 코드를 고치지 않고 반영한다는 뜻이다. XLSX만으로 홍보물 연결과 좌표를 추측하지 않는다. 새 주소의 좌표와 실제 파일·미리보기 준비는 필요하다.

## 2. 표준 패키지를 바로 교체하기

새 폴더를 다음처럼 준비한다. 기존 공고 폴더를 덮어쓰지 말고 새 공고 ID로 만든다.

```text
datasets/my-new-notice/
  dataset.json
  assets/files/...
  assets/previews/...
```

### 먼저 검증

```bash
python tools/dataset.py validate \
  --dataset datasets/my-new-notice/dataset.json \
  --asset-root datasets/my-new-notice
```

`--asset-root`는 그 아래에 `assets/`가 있는 폴더다. `assets/` 자체를 지정하지 않는다. 모든 검증을 통과하기 전에는 현재 지도 데이터가 바뀌지 않는다.

### 실제 반영 없이 준비 상태 확인

```bash
python tools/dataset.py activate \
  --dataset datasets/my-new-notice/dataset.json \
  --asset-root datasets/my-new-notice \
  --dry-run
```

### 활성화

```bash
python tools/dataset.py activate \
  --dataset datasets/my-new-notice/dataset.json \
  --asset-root datasets/my-new-notice
```

성공하면 `config/active-dataset.json`에 활성 공고·해시·자산 경로가 기록되고 `config/validation-audit.json`에 검증 결과가 기록된다. 미디어는 `dist/datasets/<공고 ID>/<내용 해시>/assets/`에 먼저 복사된다. 마지막으로 `dist/data.js`를 교체한다. 복사나 검증이 실패하면 이전 데이터 포인터를 유지한다.

로컬 서버를 실행하고 브라우저를 새로고침한다.

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

주소는 `http://127.0.0.1:8765/`다. 정적 서버 재시작이나 화면 코드 수정은 필요하지 않다. 이미 열려 있는 탭은 새로고침해야 한다. 호스팅된 사이트에는 활성화된 `dist/`를 기존 Sites 프로젝트로 다시 게시해야 반영된다. 로컬 파일 교체가 서버 배포를 자동 실행하지는 않는다.

## 3. 새 XLSX를 설정으로 가져오기

[`config/lh-current.json`](config/lh-current.json)을 새 이름으로 복사한다. 이 설정에는 현재 정정공고의 파일·시트·열 매핑이 완성되어 있다.

새 설정에서 다음 부분을 바꾼다.

1. `notice`: 새 공고 ID·원문 제목·날짜·URL·화면 제목·지역·배지·공급기관
2. `paths.xlsx`: 기준 XLSX의 정확한 경로
3. `paths.manifest`: 새 공고의 수집 명세 `manifest.json`
4. `paths.geocodes`: 원문 주소별 검증 좌표 명세
5. `paths.attachments`: 원본과 미리보기 경로가 들어 있는 첨부 명세
6. `paths.assetRoot`: 해당 파일들을 가진 자산 루트
7. `spreadsheet.fileId`, `sheetName`, `headerRow`, `dataStartRow`, `columns`

설정 안의 상대 경로는 **설정 파일이 있는 폴더** 기준이다. 공백·한글·괄호가 있는 경로를 그대로 사용할 수 있다. 명령행에 직접 쓸 때에는 따옴표로 감싼다.

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

### 추출만 먼저 검토

```bash
python tools/import_xlsx.py \
  --config config/my-new-notice.json \
  --output datasets/my-new-notice/dataset.json \
  --extract-only tmp/my-new-notice-source.json
```

이 명령은 세대 추출 결과만 만든다. `--output`의 표준 데이터나 현재 지도를 변경하지 않는다. 세대수·주소·원본 행·미기재 값을 확인한다.

### 표준 데이터 생성

```bash
python tools/import_xlsx.py \
  --config config/my-new-notice.json \
  --output datasets/my-new-notice/dataset.json
```

이 단계도 현재 지도는 변경하지 않는다. 출력된 표준 데이터에 2절의 검증·활성화를 적용한다. 일반적인 공고 교체에서 `dist/app.js`, `dist/index.html`, `dist/style.css`는 수정하지 않는다.

## 4. 이전 수집 형식에서 변환

기존 파이프라인의 자료가 이미 있으면 다음 명령으로 표준 형식에 넣을 수 있다.

```bash
python tools/dataset.py import-current \
  --notice-id my-new-notice \
  --source path/to/source-data.json \
  --geocodes path/to/geocodes.json \
  --attachments path/to/assets/attachments.json \
  --asset-root path/to/bundle-root \
  --manifest path/to/manifest.json \
  --notice-config path/to/notice-metadata.json \
  --output datasets/my-new-notice/dataset.json
```

`notice-metadata.json`은 `lh-current.json`의 `notice` 객체만 담은 파일이다. `--notice-id`와 그 객체의 `id`는 같아야 한다. 변환기는 원본 셀값·행 번호, 파일 해시, 홍보물 연결 근거를 보존한다.

## 5. PDF·이미지·평면도 연결하기

1. 실제 원본 파일을 `assets/files/`에 둔다.
2. PDF는 모든 페이지, PPTX는 모든 슬라이드를 이미지로 변환한다. 일반 이미지는 미리보기 1페이지다.
3. `media`에 원본 해시·크기·미리보기 페이지·부모 미디어 ID·썸네일을 등록한다.
4. `relations`로 공고·주택군·건물·세대 중 실제 대상을 지정한다.
5. 건물 전용으로 확정할 수 없는 주택군 공통 자료는 `match: "group"`으로 표시한다.
6. 세대 전용 평면도는 `targetType: "unit"`으로 연결한다. 다른 세대만 검색되면 해당 전용 자료는 표시하지 않는다.

PDF를 새 파일로 바꾸었다면 원본 `sha256`·`size`, 모든 페이지와 썸네일도 새로 만든다. 파일명만 바꾸고 기존 이미지 미리보기를 유지하지 않는다. 기존 파일과 다른 내용이면 검증된 새 패키지로 활성화한다.

## 6. 반영 전에 확인할 항목

- [ ] 공고 ID·제목·날짜·원문 URL이 새 공고와 일치
- [ ] 기준 XLSX·정정 여부·파일 ID가 맞음
- [ ] 모든 원본 세대 순번과 17개 표준 항목이 보존됨
- [ ] 미기재 면적·승강기 등을 0·없음으로 임의 치환하지 않음
- [ ] 원문 주소마다 검증 좌표와 출처가 있음
- [ ] 모든 PDF 페이지와 이미지 부모 관계가 맞음
- [ ] 주택군 공통 자료와 특정 세대 자료의 관계가 구분됨
- [ ] `validate`와 `activate --dry-run` 통과
- [ ] 활성화 후 제목·세대수·주소수·필터·홍보물 미리보기 확인
- [ ] 지역·방수 등을 복수 선택했을 때 검색된 건물만 지도에 표시됨
- [ ] 호스팅 사이트를 사용하는 경우 새 버전 게시 완료

## 7. 오류와 되돌리기

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

실패한 활성화는 기존 데이터 포인터를 유지한다. 이미 성공한 교체를 되돌리려면 이전 공고의 표준 패키지로 `activate`를 다시 실행한다. 이전 스냅샷은 열려 있는 탭의 자료 링크를 위해 보존한다. 사용 중인 스냅샷을 무작정 삭제하지 않는다.

`build`로 별도 검토용 출력도 만들 수 있다.

```bash
python tools/dataset.py build \
  --dataset datasets/my-new-notice/dataset.json \
  --asset-root datasets/my-new-notice \
  --output tmp/review-build
```

이는 데이터·미디어 출력이며 전체 지도 앱의 HTML·CSS까지 복제하는 명령은 아니다. 검토 후 활성화를 별도로 실행한다.
