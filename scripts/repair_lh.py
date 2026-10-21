import os,json,re
from pathlib import Path
workspace=Path(__file__).resolve().parents[1]
root=Path(os.environ.get('LH_OUTPUT_ROOT',str(workspace/'data/notices'/('lh_'+os.environ.get('LH_PAN_ID','2015122300020927')))))
d=json.loads((root/'manifest.json').read_text())
embedded=re.findall(r"list = JSON.parse\('(\[.*?\])'\);",Path('/tmp/lh_notice_new.html').read_text())
housing_rows=next(json.loads(x) for x in embedded if json.loads(x))
names={x['aptBrndCd']:x['dngHsAdr'] for x in housing_rows}
def fix(s):
    try: return s.encode('latin1').decode('utf8')
    except (UnicodeEncodeError,UnicodeDecodeError): return s
for p in d['popups']:
    p['housing']=names[p['apt']]
    for i in p['items']:
        for k,v in i.items():
            if isinstance(v,str): i[k]=fix(v)
for r in d['records']:
    if r['kind']!='홍보물': continue
    r.update(housing=names[r['apt']],name=fix(r['name']),address=fix(r['address']))
    if r['path']:
        old=root/r['path']
        folder=root/'홍보물'/re.sub(r'[\\/:*?"<>|]','_',r['housing'])
        addresses={x['address'] for x in d['records'] if x.get('housing')==r['housing']}
        if len(addresses)>1:
            folder=folder/re.sub(r'[\\/:*?"<>|]','_',r['address'])
        folder.mkdir(parents=True,exist_ok=True)
        new=folder/(r['id']+'_'+re.sub(r'[\\/:*?"<>|]','_',r['name']))
        if old!=new: old.rename(new)
        r['path']=str(new.relative_to(root))
d['housingRows']=housing_rows
(root/'manifest.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
(root/'popup_raw.json').write_text(json.dumps(d['popups'],ensure_ascii=False,indent=2))
print('수정 완료:',d['records'][4]['name'],d['records'][4]['address'])
print('확장자:',sorted(set(Path(r['name']).suffix for r in d['records'])))
print('홍보물 없음:',[p['housing'] for p in d['popups'] if not p['items']])
