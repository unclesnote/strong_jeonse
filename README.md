# 든든전세 지도

2026.09.30 경기남부 든든전세 정정공고의 주택목록과 홍보물을 함께 보는 정적 웹 페이지입니다.

## 실행

프로젝트 폴더에서 `python -m http.server 8765 --bind 127.0.0.1 --directory dist`를 실행하고 `http://127.0.0.1:8765/`를 여세요. 별도 설치나 API 키는 필요하지 않습니다. 지도 배경에는 인터넷 연결이 필요합니다.

## 데이터 기준

- 공고 식별값: `2015122300020927`
- 정정 주택목록 엑셀: `69044664`
- 원본 344세대, 56개 주소 문자열, 38개 주택군의 17개 열을 보존합니다.
- 실사용면적이 비어 있는 4세대는 빈값으로 유지합니다.
- 원문 주소별 지도 마커를 만들고, 같은 위치는 묶어서 선택합니다. 임의 좌표 이동은 하지 않습니다.
- 미디어 연결은 주소 일치, 같은 위치, 같은 주택군의 세 단계로 표시합니다. 공통 홍보물을 다른 건물의 전용 자료로 표시하지 않습니다.
- PDF와 PPTX의 모든 페이지를 WebP 이미지로 변환했습니다. XLSX는 원본 다운로드를 제공합니다.

## 새 공고 교체

표준 패키지를 준비하면 화면 코드를 수정하지 않고 교체할 수 있습니다. [데이터 교체 가이드](DATA_GUIDE.md), [PDF·이미지 관계 표준](DATA_STANDARD.md), [JSON 스키마](schema/notice-dataset.schema.json)를 참고하세요.

```bash
python tools/dataset.py validate --dataset datasets/공고ID/dataset.json --asset-root datasets/공고ID
python tools/dataset.py activate --dataset datasets/공고ID/dataset.json --asset-root datasets/공고ID
```

활성화 후 브라우저를 새로고침합니다. 실제 호스팅 사이트는 새 `dist/`를 다시 게시해야 합니다. `dist/data.js`는 생성물이므로 직접 수정하지 않습니다. 새 XLSX는 `tools/import_xlsx.py`와 `config/lh-current.json`의 시트·열 매핑으로 표준 패키지에 넣습니다.

기존 수집·변환 도구도 남겨 두었습니다. 상위 `collect_lh.py`는 `LH_PAN_ID`와 `LH_NOTICE_HTML`을 받아 첨부를 수집합니다. `prepare_site_assets.py`에는 Pillow, Poppler, LibreOffice가 필요합니다. `geocode_addresses.py`는 한 번 수집한 주소 검색 응답을 `tmp/`에 저장해 재사용하며 페이지 이용 중에는 주소 검색 API를 호출하지 않습니다. 중간 산출물은 `tools/dataset.py import-current`로 변환합니다. `build_data.py`는 표준 활성화 명령의 호환 진입점입니다.

`media-sync-audit.json`은 원본 세대 정보 보존, 좌표와 미디어 연결, 파일 경로 검증 결과입니다. `source-data.json`에는 원본 엑셀의 각 셀 값과 행 번호가 있습니다.

주요 기능 설계와 구현 체크리스트, 원본 대조 검증 결과는 [design.md](design.md)에 기록합니다. 지역·보증금·면적·방수·유형·승강기 필터는 각각 복수 선택할 수 있습니다. 같은 항목 안에서는 OR, 서로 다른 항목 사이에서는 AND로 결합하며, 일치하는 세대가 있는 건물만 목록과 지도에 함께 표시합니다.

## 지도와 라이브러리

지도 배경: [OpenStreetMap](https://www.openstreetmap.org/copyright). 지도 UI: [Leaflet](https://leafletjs.com/), [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster). 좌표 확인: 카카오맵 공개 주소 검색. 공고와 첨부파일의 출처는 화면의 LH 원문 링크와 원본 다운로드에 표시합니다.

서버나 로그인 처리 없이 브라우저에서 검색·정렬·필터를 실행합니다. 저장한 건물은 해당 브라우저의 로컬 저장소에 보관됩니다.
