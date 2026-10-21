#!/usr/bin/env python3
"""Configurable XLSX-to-standard-dataset adapter. Does not activate or overwrite a live site."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NUMBERS={'id','area','expandedArea','exclusiveArea','rooms','deposit'}
FIELDS=['id','province','supplyRegion','group','address','building','unit','areaBand','area','expandedArea','exclusiveArea','rooms','floor','elevator','type','deposit','notes']

def read_sheet(path,sheet_name):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=workbook.findall('m:sheets/m:sheet',NS)
        selected=[s for s in sheets if s.get('name')==sheet_name]
        if len(selected)!=1: raise ValueError(f'시트를 찾을 수 없습니다: {sheet_name}. 실제 시트: {[s.get("name") for s in sheets]}')
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rid=selected[0].get('{'+REL+'}id')
        target=next((r.get('Target') for r in rels if r.get('Id')==rid),None)
        if not target:raise ValueError('워크시트 관계 경로가 없습니다.')
        sheet_path=target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl')/target)
        tree=ET.fromstring(z.read(sheet_path)); result={}
        for row in tree.findall('m:sheetData/m:row',NS):
            raw={}; formulas=[]
            for c in row:
                ref=c.get('r');col=re.sub('[0-9]','',ref);value=c.find('m:v',NS);inline=c.find('m:is',NS)
                if c.find('m:f',NS)is not None and value is None:formulas.append(ref)
                raw[col]=strings[int(value.text)] if c.get('t')=='s' and value is not None else ''.join(inline.itertext()) if inline is not None else value.text if value is not None and value.text is not None else ''
            result[int(row.get('r'))]=(raw,formulas)
        return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--extract-only',type=Path,help='검토할 source-data JSON만 작성하고 표준 변환은 하지 않음')
    args=p.parse_args();config_path=args.config.resolve();config=json.loads(config_path.read_text(encoding='utf-8'))
    def path(key):
        value=Path(config['paths'][key]);return value if value.is_absolute() else (config_path.parent/value).resolve()
    notice=config['notice'];spec=config['spreadsheet'];source_path=path('xlsx')
    manifest=json.loads(path('manifest').read_text(encoding='utf-8'))
    rows=read_sheet(source_path,spec['sheetName']);header=rows.get(spec['headerRow'],({},[]))[0]
    mapping={}
    for field,selector in spec['columns'].items():
        if selector is None:mapping[field]=None;continue
        if isinstance(selector,dict):
            label=selector['header'];matches=[c for c,v in header.items() if re.sub(r'\s+','',v)==re.sub(r'\s+','',label)]
            if len(matches)!=1:raise ValueError(f'열 이름이 없거나 중복됩니다: {label}')
            mapping[field]=matches[0]
        elif isinstance(selector,str) and re.fullmatch('[A-Z]+',selector):mapping[field]=selector
        else:raise ValueError(f'잘못된 열 매핑: {field}={selector!r}')
    for required in ['id','group','address']:
        if not mapping.get(required):raise ValueError(f'필수 열 매핑 누락: {required}')
    aliases=config.get('groupAliases',{});units=[]
    yes=set(spec.get('elevatorYesValues',['Y','있음']));no=set(spec.get('elevatorNoValues',['N','없음']))
    for rowno,(raw,formulas) in sorted(rows.items()):
        if rowno<spec['dataStartRow'] or not any(str(v).strip() for v in raw.values()):continue
        if not str(raw.get(mapping['id'],'')).strip():continue
        if formulas:raise ValueError(f'캐시 값이 없는 수식이 있습니다: {formulas}. 엑셀에서 계산 후 저장하세요.')
        values={f:raw.get(mapping.get(f),'') if mapping.get(f) else '' for f in FIELDS}
        unit={}
        for field,value in values.items():
            text=str(value).strip()
            if field=='id':
                if not text:raise ValueError(f'순번이 없습니다: {rowno}행')
                id_type=spec.get('idType','auto')
                if id_type not in ('auto','string','integer'):raise ValueError('spreadsheet.idType은 auto/string/integer 중 하나여야 합니다.')
                if id_type=='integer':
                    if not re.fullmatch('[0-9]+',text):raise ValueError(f'정수 순번이 아닙니다: {rowno}행 {text!r}')
                    unit[field]=int(text)
                elif id_type=='string':unit[field]=text
                else:unit[field]=int(text) if re.fullmatch('(0|[1-9][0-9]*)',text) else text
            elif field in NUMBERS:
                if not text:unit[field]=None
                else:
                    try:unit[field]=float(text.replace(',',''))
                    except ValueError:raise ValueError(f'숫자가 아닌 값: {rowno}행 {field}={text!r}')
            elif field=='elevator':
                if not text:unit[field]=None
                elif text in yes:unit[field]=True
                elif text in no:unit[field]=False
                else:raise ValueError(f'승강기 값 매핑 필요: {rowno}행 {text!r}')
            else:unit[field]=str(value)
        if not unit['address'].strip() or not unit['group'].strip():raise ValueError(f'주소 또는 주택군이 없습니다: {rowno}행')
        if unit['group'] in aliases:unit['originalGroup']=unit['group'];unit['group']=aliases[unit['group']]
        unit.update(sourceRow=rowno,rawFields=raw)
        units.append(unit)
    if not units:raise ValueError('읽은 세대가 0개입니다. 시트·데이터 시작 행·열 매핑을 확인하세요.')
    file_id=str(spec['fileId']);inventory=[r for r in manifest['records'] if str(r['id'])==file_id and r.get('path')]
    if len(inventory)!=1 or Path(inventory[0]['path']).suffix.lower()!='.xlsx':raise ValueError('지정한 XLSX fileId가 수집 명세의 다운로드 파일과 일치하지 않습니다.')
    if Path(inventory[0]['path']).name!=source_path.name:raise ValueError('XLSX 경로와 fileId의 파일명이 다릅니다. 잘못된 공고를 결합하지 않도록 확인하세요.')
    brochures=[dict(r,housing=aliases.get(r['housing'],r['housing'])) for r in manifest['records'] if r.get('path') and r['kind']=='홍보물']
    source={'title':notice['title'],'sourceUrl':notice['sourceUrl'],'noticeDate':notice['noticeDate'],'collectedDate':notice['collectedDate'],'units':units,'brochures':brochures,'commonFiles':[str(r['id']) for r in manifest['records'] if r.get('path') and r['kind']=='공고 첨부'],'housing':manifest.get('housingRows',[]),'spreadsheet':{'id':file_id,'name':source_path.name,'sheetName':spec['sheetName'],'columns':{mapping[f]:header.get(mapping[f],f).replace('\n',' ') for f in mapping if mapping[f]},'notices':[r[0]['A'] for n,r in rows.items() if n<spec['headerRow'] and r[0].get('A')]}}
    if args.extract_only:
        args.extract_only.parent.mkdir(parents=True,exist_ok=True);args.extract_only.write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8');print(f'추출 완료: {len(units)}세대 -> {args.extract_only}');return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='notice-import-') as t:
        temp=Path(t);src=temp/'source.json';meta=temp/'notice.json'
        src.write_text(json.dumps(source,ensure_ascii=False),encoding='utf-8');meta.write_text(json.dumps(notice,ensure_ascii=False),encoding='utf-8')
        command=[sys.executable,str(ROOT/'scripts/dataset.py'),'import-current','--notice-id',notice['id'],'--source',str(src),'--geocodes',str(path('geocodes')),'--attachments',str(path('attachments')),'--asset-root',str(path('assetRoot')),'--manifest',str(path('manifest')),'--notice-config',str(meta),'--output',str(args.output.resolve())]
        subprocess.run(command,check=True)
    print(f'표준 데이터 생성 완료: {len(units)}세대 -> {args.output}')

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,zipfile.BadZipFile,subprocess.CalledProcessError) as e:print(f'가져오기 실패: {e}',file=sys.stderr);sys.exit(1)
