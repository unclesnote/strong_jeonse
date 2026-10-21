import json,re,time,hashlib,concurrent.futures,os
from pathlib import Path
import requests
from bs4 import BeautifulSoup

PAN_ID=os.environ.get('LH_PAN_ID','2015122300020927')
WORKSPACE=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('LH_OUTPUT_ROOT',str(WORKSPACE/'data/notices'/('lh_'+PAN_ID))))
ROOT.mkdir(parents=True,exist_ok=True)
BASE='https://apply.lh.or.kr'
URL=BASE+'/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId='+PAN_ID+'&ccrCnntSysDsCd=03&uppAisTpCd=13&aisTpCd=26&mi=1026'
URL=os.environ.get('LH_NOTICE_URL',URL)
soup=BeautifulSoup(Path(os.environ.get('LH_NOTICE_HTML','/tmp/lh_notice_new.html')).read_text(),'html.parser')
embedded=re.findall(r"list = JSON.parse\('(\[.*?\])'\);",str(soup))
housing_rows=next(json.loads(x) for x in embedded if json.loads(x))
housing_names={x['aptBrndCd']:x['dngHsAdr'] for x in housing_rows}
records=[]
for a in soup.select('a[href*=fileDownLoad]'):
    m=re.search(r"fileDownLoad\('([^']+)'",a['href'])
    if m: records.append(dict(kind='공고 첨부',name=a.get_text(strip=True),id=m[1],housing='',address='',source=URL))
popups={}
for a in soup.select('a[href*=ahflPop]'):
    args=re.findall(r"'([^']*)'",a['href'])
    key=tuple(args[1:])
    if key not in popups:
        tr=a.find_parent('tr')
        cells=[c.get_text(' ',strip=True) for c in tr.find_all('td')]
        popups[key]=dict(count=int(args[0]),sbd=key[0],dng=key[1],apt=key[2],housing=housing_names.get(key[2],cells[1]),row=cells)

def get_popup(p):
    if not p['count']: return dict(**p,items=[])
    endpoint='/lhapply/apply/wt/wrtanc/'+('selectListAptBrndAhfInf.do' if p['apt'] else 'selectWrtancAhflInfList.do')
    data={'sbdLgoNo':p['sbd']}
    data.update({'aptBrndCd':p['apt']} if p['apt'] else {'dngHsAdmNo':p['dng']})
    for attempt in range(3):
        try:
            r=requests.post(BASE+endpoint,data=data,headers={'Referer':URL},timeout=40)
            r.raise_for_status()
            return dict(**p,items=json.loads(r.content.decode('utf-8'))['list'],endpoint=BASE+endpoint)
        except Exception:
            if attempt==2: raise
            time.sleep(1)

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    results=list(ex.map(get_popup,popups.values()))
for p in results:
    for item in p['items']:
        records.append(dict(kind='홍보물',housing=p['housing'],address=item.get('dngHsAdr',''),name=item['cmnAhflNm'],id=str(item['cmnAhflSn']),source=p['endpoint'],apt=p['apt']))
print('popups',len(results),'nonempty',sum(bool(x['items']) for x in results),'records',len(records),flush=True)
(ROOT/'popup_raw.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))

unique={}
for r in records:
    r['url']=BASE+'/lhapply/lhFile.do?fileid='+r['id']
    if Path(r['name']).suffix.lower() in ('.hwp','.hwpx'):
        r['status']='제외('+Path(r['name']).suffix.lstrip('.').upper()+')';r['path']='';r['size']=None
    else: unique.setdefault(r['id'],r)

def download(r):
    folder='공고첨부' if r['kind']=='공고 첨부' else '홍보물/'+re.sub(r'[\\/:*?"<>|]','_',r['housing'])
    if r['kind']=='홍보물' and len({x['address'] for x in records if x.get('housing')==r['housing']})>1: folder+='/'+re.sub(r'[\\/:*?"<>|]','_',r['address'])
    path=ROOT/folder/(r['id']+'_'+re.sub(r'[\\/:*?"<>|]','_',r['name']))
    path.parent.mkdir(parents=True,exist_ok=True)
    resp=requests.get(r['url'],headers={'Referer':URL},timeout=120)
    resp.raise_for_status()
    if 'text/html' in resp.headers.get('content-type',''): raise ValueError('HTML instead of file: '+r['id'])
    path.write_bytes(resp.content)
    return r['id'],dict(path=str(path.relative_to(ROOT)),size=len(resp.content),sha256=hashlib.sha256(resp.content).hexdigest(),status='다운로드 완료',contentType=resp.headers.get('content-type',''))

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    downloaded=dict(ex.map(download,unique.values()))
for r in records:
    if r['id'] in downloaded: r.update(downloaded[r['id']])
manifest=dict(title=soup.select_one('.bbs_ViewA h3').get_text(strip=True),url=URL,popups=results,records=records,housingRows=housing_rows)
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('downloaded',len(downloaded),'bytes',sum(x['size'] for x in downloaded.values()),'excluded',sum(x['status'].startswith('제외') for x in records),flush=True)
