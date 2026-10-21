#!/usr/bin/env python3
"""One-time cached public Kakao Map address lookup; no API credentials or site-side geocoding."""
from pathlib import Path
import json,re,time,requests,hashlib,os
ROOT=Path(__file__).resolve().parent
source=json.loads((ROOT/'source-data.json').read_text()); manifest=json.loads((ROOT.parents[1]/'outputs'/('lh_'+os.environ.get('LH_PAN_ID','2015122300020927'))/'manifest.json').read_text())
addresses=list(dict.fromkeys([u['address'] for u in source['units']]+[r['address'] for r in manifest['records'] if r.get('address')]))
CACHE=ROOT/'tmp/geocode-cache';CACHE.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 JeonseMapResearch/1.0','Referer':'https://map.kakao.com/'})
def normalize(a):
 q=a.split('(')[0].strip().replace('병점구 ','')
 q=q.replace('영통구 원천동 영통구 원천동','영통구 원천동')
 q=re.sub(r'(\d+-\d+),\d+-\d+',r'\1',q)
 return q
out={}
for address in addresses:
 q=normalize(address); file=CACHE/(hashlib.sha256(q.encode()).hexdigest()+'.json')
 if file.exists(): data=json.loads(file.read_text())
 else:
  r=s.get('https://search.map.kakao.com/mapsearch/map.daum',params={'q':q,'msFlag':'A','output':'json'},timeout=25);r.raise_for_status();r.encoding='utf-8';data=r.json();file.write_text(json.dumps(data,ensure_ascii=False,indent=2));time.sleep(.6)
 matches=data.get('address',[])
 exact=[]
 # Require the exact street/lot and number token from the query to appear in result address.
 key=q.replace('경기도 ','').strip()
 for m in matches:
  ma=m.get('addr','').replace('경기 ','').replace('병점구 ','').strip()
  if ma==key and m.get('lat') and m.get('lon'): exact.append(m)
 if not exact and len(matches)==1:
  m=matches[0];ma=m.get('addr','').replace('경기 ','').replace('병점구 ','').strip()
  if q.replace('경기도 ','').strip()==ma and m.get('lat') and m.get('lon'):exact=[m]
 if exact:
  m=exact[0]; out[address]={'lat':float(m['lat']),'lng':float(m['lon']),'query':q,'source':'https://search.map.kakao.com/mapsearch/map.daum?q='+requests.utils.quote(q),'precision':'street-address' if m.get('data_type')=='5' else 'lot-address','status':'validated','matchedAddress':m['addr'],'buildingName':m.get('building_name','')}
 else:out[address]={'lat':None,'lng':None,'query':q,'source':'https://search.map.kakao.com/mapsearch/map.daum?q='+requests.utils.quote(q),'precision':None,'status':'unresolved','candidates':[{'address':m.get('addr'),'lat':m.get('lat'),'lng':m.get('lon')} for m in matches]}
 (ROOT/'geocodes.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(out[address]['status'],address,flush=True)
print('COVERAGE',sum(x['status']=='validated' for x in out.values()),'/',len(out))
