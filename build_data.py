#!/usr/bin/env python3
"""Compile authoritative XLSX-derived units with validated positions and source media."""
from pathlib import Path
from collections import defaultdict,Counter
import json,re,hashlib
ROOT=Path(__file__).resolve().parent
source=json.loads((ROOT/'source-data.json').read_text())
geocodes=json.loads((ROOT/'geocodes.json').read_text())
attachments=json.loads((ROOT/'dist/assets/attachments.json').read_text())
def norm(address):return re.sub(r'\s+',' ',address).strip()
def same_location(a,b):
 ga=geocodes.get(a);gb=geocodes.get(b)
 return bool(ga and gb and ga['status']=='validated' and gb['status']=='validated' and abs(ga['lat']-gb['lat'])<1e-7 and abs(ga['lng']-gb['lng'])<1e-7)
by_address={}
for unit in source['units']:by_address.setdefault(unit['address'],[]).append(unit)
buildings=[];audit_buildings=[]
for index,(address,units) in enumerate(by_address.items(),1):
 groups=set(u['group'] for u in units);assert len(groups)==1,(address,groups)
 group=units[0]['group'];geo=geocodes[address];assert geo['status']=='validated'
 media=[]
 for record in source['brochures']:
  if record['housing']!=group:continue
  ident=str(record['id']);assert ident in attachments
  match='address' if norm(record['address'])==norm(address) else 'location' if same_location(record['address'],address) else 'group'
  media.append({**attachments[ident],'match':match,'sourceAddress':record['address'],'sourceUrl':record['url']})
 media.sort(key=lambda m:({'address':0,'location':1,'group':2}[m['match']],m['id']))
 b={'id':f'b{index:03d}','group':group,'address':address,'city':address.split()[1],'lat':geo['lat'],'lng':geo['lng'],'coordinateSource':geo['source'],'matchedAddress':geo['matchedAddress'],'units':units,'unitCount':len(units),'minDeposit':min(u['deposit'] for u in units),'maxDeposit':max(u['deposit'] for u in units),'minArea':min((u['area'] for u in units if u['area'] is not None),default=None),'maxArea':max((u['area'] for u in units if u['area'] is not None),default=None),'rooms':sorted(set(u['rooms'] for u in units)),'types':sorted(set(u['type'] for u in units)),'elevator':any(u['elevator'] for u in units),'media':media,'thumbnail':next((m['thumbnail'] for m in media if m.get('thumbnail')),None)}
 buildings.append(b)
 audit_buildings.append({'id':b['id'],'group':group,'address':address,'units':len(units),'mediaCount':len(media),'matches':dict(Counter(m['match'] for m in media)),'media':[{'id':m['id'],'match':m['match'],'sourceAddress':m['sourceAddress']} for m in media]})
meta={k:source[k] for k in ['title','sourceUrl','noticeDate','collectedDate']}
meta.update(totalUnits=len(source['units']),totalBuildings=len(buildings),totalGroups=len(set(u['group'] for u in source['units'])),commonFiles=[attachments[str(ident)] for ident in source['commonFiles']],coordinateAttribution='주소 위치: 카카오맵 공개 주소 검색 · 원본 주소: LH 주택목록')
meta['spreadsheet']=source.get('spreadsheet',{})
data={'meta':meta,'buildings':buildings,'attachments':attachments,'housing':source.get('housing',[])}
compiled=sorted((u for b in buildings for u in b['units']),key=lambda u:u['id'])
original=sorted(source['units'],key=lambda u:u['id'])
assert compiled==original,'Unit field data changed'
assert len(set(u['id'] for u in compiled))==len(original)
assert len(buildings)==len(by_address)
assert set(u['address'] for u in original)==set(b['address'] for b in buildings)
assert all(m['id'] in attachments for b in buildings for m in b['media'])
assert set(r['id'] for r in source['brochures'])==set(m['id'] for b in buildings for m in b['media'])
for attachment in attachments.values():
 for path in [attachment['url']]+attachment['pages']+([attachment['thumbnail']] if attachment['thumbnail'] else []):assert (ROOT/'dist'/path).is_file(),path
(ROOT/'dist/data.js').write_text('window.JEONSE_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
audit={'authoritativeSource':'source-data.json units derived from LH source XLSX','sourceSHA256':hashlib.sha256((ROOT/'source-data.json').read_bytes()).hexdigest(),'validation':{'allOriginalUnitFieldsPreserved':compiled==original,'sourceMissingAreaIds':[u['id'] for u in original if u['area'] is None],'uniqueUnitIds':len(set(u['id'] for u in compiled)),'unitCount':len(compiled),'exactSourceAddresses':len(buildings),'groups':meta['totalGroups'],'allCoordinatesValidated':all(geocodes[b['address']]['status']=='validated' for b in buildings),'allAttachmentIdsValid':True,'allBrochureFilesReachable':True,'allPreviewAndOriginalPathsExist':True},'mediaSync':{'attachmentCount':len(attachments),'brochureCount':len(source['brochures']),'bindingsByMatch':dict(Counter(m['match'] for b in buildings for m in b['media'])),'buildingsWithoutAnyMedia':[b['id'] for b in buildings if not b['media']],'buildingsWithoutExactOrLocationMedia':[b['id'] for b in buildings if not any(m['match']!='group' for m in b['media'])],'matchExplanation':{'address':'Whitespace-normalized source address matches exactly','location':'Same group; validated road or lot address resolves to same position','group':'Same source housing group; may depict another building, so not claimed as exact building media'}},'buildings':audit_buildings}
(ROOT/'media-sync-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
print(json.dumps({'meta':meta,'validation':audit['validation'],'mediaSync':audit['mediaSync']},ensure_ascii=False,indent=2))
