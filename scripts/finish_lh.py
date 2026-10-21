import os,json,zipfile,hashlib
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as E
workspace=Path(__file__).resolve().parents[1]
root=Path(os.environ.get('LH_OUTPUT_ROOT',str(workspace/'data/notices'/('lh_'+os.environ.get('LH_PAN_ID','2015122300020927')))))
d=json.loads((root/'manifest.json').read_text())
file=root/'LH_든든전세_첨부파일정리.xlsx'
ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
rn='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
pn='http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('',ns)
E.register_namespace('r',rn)
with zipfile.ZipFile(file) as z: contents={n:z.read(n) for n in z.namelist()}
for idx in (1,2):
    name=f'xl/worksheets/sheet{idx}.xml'
    sheet=E.fromstring(contents[name])
    for old in list(sheet.findall('{'+ns+'}hyperlinks')): sheet.remove(old)
    links=E.Element('{'+ns+'}hyperlinks')
    rels=E.Element('{'+pn+'}Relationships')
    pairs=[('B4',d['url'])]
    if idx==1:
        for i,r in enumerate(d['records'],7):
            if r['path']: pairs.append((f'I{i}',quote(r['path'],safe='/()_-.')))
            pairs.append((f'J{i}',r['url']))
    for i,(cell,target) in enumerate(pairs,1):
        rid=f'rIdLH{i}'
        E.SubElement(links,'{'+ns+'}hyperlink',{'ref':cell,'{'+rn+'}id':rid})
        E.SubElement(rels,'{'+pn+'}Relationship',{'Id':rid,'Type':rn+'/hyperlink','Target':target,'TargetMode':'External'})
    insert=next((i for i,x in enumerate(sheet) if x.tag.split('}')[-1] in ('printOptions','pageMargins','pageSetup','headerFooter','drawing','tableParts','extLst')),len(sheet))
    sheet.insert(insert,links)
    contents[name]=E.tostring(sheet,encoding='utf-8',xml_declaration=True)
    contents[f'xl/worksheets/_rels/sheet{idx}.xml.rels']=E.tostring(rels,encoding='utf-8',xml_declaration=True)
temp=file.with_suffix('.tmp')
with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
    for n,b in contents.items(): z.writestr(n,b)
temp.replace(file)
paths=set()
for r in d['records']:
    if not r['path']: continue
    p=root/r['path']
    assert p.exists(),p
    assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],p
    assert p.suffix.lower() not in ('.hwp','.hwpx')
    paths.add(p)
assert len(paths)==len({r['id'] for r in d['records'] if r['path']})
archive=Path(os.environ.get('LH_ARCHIVE',str(workspace/'outputs/LH_든든전세_정정공고_건물별_첨부파일.zip')))
archive.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(paths|{file}):z.write(p,arcname=p.relative_to(root))
print(f'검증 완료: {len(paths)}개 파일, 주택군 {len(d["popups"])}개, HWP/HWPX 없음, 한글 이름 보존')
print(archive)
