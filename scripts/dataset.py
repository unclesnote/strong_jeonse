#!/usr/bin/env python3
"""Versioned notice data: import, validate, build and transactionally activate.

Canonical paths are always assets/... relative to --asset-root. Activation copies
all referenced assets into an immutable content-addressed snapshot before the
single live browser data pointer is replaced. No API credentials or network use.
"""
from __future__ import annotations
import argparse, collections, contextlib, copy, datetime, hashlib, json, math, os
from pathlib import Path, PurePosixPath
import re, shutil, struct, subprocess, sys, tempfile, urllib.parse, uuid, zipfile
import jsonschema

PROJECT = Path(__file__).resolve().parents[1]
SCHEMA = PROJECT / 'data/schema/notice-dataset.schema.json'
VERSION = '1.0.0'
class DatasetError(ValueError): pass

def read_json(path):
    with Path(path).open(encoding='utf-8') as f: return json.load(f,parse_constant=lambda value: (_ for _ in ()).throw(DatasetError('Non-finite JSON number: '+value)))
def encode_json(value): return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
def stable(notice,kind,*values):
    h=hashlib.sha256(json.dumps(values,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:20]
    return f'{notice}:{kind}:{h}'
def local_file(root,url):
    if not isinstance(url,str): raise DatasetError('Asset URL must be text')
    decoded=url
    for _ in range(3): decoded=urllib.parse.unquote(decoded)
    p=PurePosixPath(decoded)
    if (url!=decoded or not url.startswith('assets/') or '\\' in url or ':' in url or '?' in url or '#' in url or p.is_absolute() or any(x in ('','.','..') for x in url.split('/'))):
        raise DatasetError(f'Unsafe local asset path: {url!r}')
    root=Path(root).resolve();file=(root/url).resolve()
    try: file.relative_to(root)
    except ValueError: raise DatasetError(f'Asset escapes asset root: {url}')
    if not file.is_file(): raise DatasetError(f'Missing asset: {file}')
    return file

def image_dimensions(path):
    """Read PNG/JPEG/WebP dimensions without image authoring dependencies."""
    with Path(path).open('rb') as f:
        head=f.read(32)
        if head[:8]==b'\x89PNG\r\n\x1a\n': return struct.unpack('>II',head[16:24])
        if head[:4]==b'RIFF' and head[8:12]==b'WEBP':
            chunk=head[12:16]
            if chunk==b'VP8X': return int.from_bytes(head[24:27],'little')+1,int.from_bytes(head[27:30],'little')+1
            if chunk==b'VP8 ' and head[23:26]==b'\x9d\x01\x2a': return struct.unpack('<H',head[26:28])[0]&0x3fff,struct.unpack('<H',head[28:30])[0]&0x3fff
            if chunk==b'VP8L' and head[20]==0x2f:
                bits=int.from_bytes(head[21:25],'little');return (bits&0x3fff)+1,((bits>>14)&0x3fff)+1
        if head[:2]==b'\xff\xd8':
            f.seek(2)
            while True:
                b=f.read(1)
                if not b: break
                if b!=b'\xff': continue
                while b==b'\xff': b=f.read(1)
                marker=b[0]
                if marker in (0xd8,0xd9):continue
                length=struct.unpack('>H',f.read(2))[0]
                if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                    _,height,width=struct.unpack('>BHH',f.read(5));return width,height
                f.seek(length-2,1)
    raise DatasetError(f'Unsupported or invalid preview image: {path}')

def asset_urls(data):
    urls=set()
    for m in data['media']:
        urls.add(m['original']['url'])
        urls.update(p['url'] for p in m['preview']['pages'])
        if m['preview']['thumbnail']:urls.add(m['preview']['thumbnail']['url'])
    return sorted(urls)

def validate(data,asset_root):
    schema=read_json(SCHEMA)
    try:json.dumps(data,allow_nan=False)
    except ValueError as e:raise DatasetError('Non-finite JSON number: '+str(e))
    try: jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(data)
    except jsonschema.ValidationError as e:raise DatasetError(f'Schema {"/".join(map(str,e.absolute_path))}: {e.message}')
    notice=data['notice'];nid=notice['id']
    if nid in ('.','..'):raise DatasetError('Unsafe notice id')
    indexes={};seen_all=set()
    for kind in ('groups','buildings','units','media','relations'):
        indexes[kind]={}
        for item in data[kind]:
            ident=item['id']
            if ident in seen_all: raise DatasetError(f'Duplicate ID: {ident}')
            if not ident.startswith(nid+':'):raise DatasetError(f'ID must be namespaced by notice id: {ident}')
            seen_all.add(ident);indexes[kind][ident]=item
    for g in data['groups']:
        if g['id']!=stable(nid,'group',g['name']):raise DatasetError(f'Unstable group ID: {g["id"]}')
    if len({g['name'] for g in data['groups']})!=len(data['groups']):raise DatasetError('Duplicate group name')
    seen_addresses=set()
    for b in data['buildings']:
        if b['groupId'] not in indexes['groups']:raise DatasetError(f'Unknown building groupId: {b["groupId"]}')
        address_key=(b['groupId'],b['address'])
        if address_key in seen_addresses:raise DatasetError(f'Duplicate building group/address: {b["address"]}')
        seen_addresses.add(address_key)
        if b['id']!=stable(nid,'building',indexes['groups'][b['groupId']]['name'],b['address']):raise DatasetError(f'Unstable building ID: {b["id"]}')
        for key in ('lat','lng'):
            if not math.isfinite(b['location'][key]):raise DatasetError('Non-finite coordinate')
    original_ids=set();used_buildings=set()
    for u in data['units']:
        b=indexes['buildings'].get(u['buildingId'])
        if b is None:raise DatasetError(f'Unknown unit buildingId: {u["buildingId"]}')
        if u['group']!=indexes['groups'][b['groupId']]['name'] or u['address']!=b['address']:raise DatasetError(f'Unit group/address differs from building: {u["id"]}')
        typed_id=(type(u['originalId']).__name__,u['originalId'])
        if typed_id in original_ids:raise DatasetError(f'Duplicate original unit ID: {u["originalId"]}')
        original_ids.add(typed_id);used_buildings.add(b['id'])
        if u['id']!=stable(nid,'unit',u['group'],u['address'],u['originalId']):raise DatasetError(f'Unstable unit ID: {u["id"]}')
        for key in ('area','expandedArea','exclusiveArea','rooms','deposit'):
            if u.get(key) is not None and (isinstance(u[key],bool) or not math.isfinite(u[key])):raise DatasetError(f'Non-numeric {key}: {u["id"]}')
    if used_buildings!=set(indexes['buildings']):raise DatasetError('Every building must have at least one source unit')
    used_groups={b['groupId'] for b in data['buildings']}
    if used_groups!=set(indexes['groups']):raise DatasetError('Every group must have at least one building')
    source_ids=set();file_hashes={};file_paths={};page_total=0;pdf_checks=0
    for url in asset_urls(data):
        file=local_file(asset_root,url);file_paths[url]=file;file_hashes[url]=digest(file)
    for m in data['media']:
        if m['provenance']['sourceId'] in source_ids:raise DatasetError('Duplicate media provenance.sourceId')
        source_ids.add(m['provenance']['sourceId'])
        original=file_paths[m['original']['url']]
        if file_hashes[m['original']['url']]!=m['original']['sha256']:raise DatasetError(f'Original SHA256 mismatch: {m["id"]}')
        if original.stat().st_size!=m['original']['size']:raise DatasetError(f'Original size mismatch: {m["id"]}')
        if original.suffix.lower() in ('.hwp','.hwpx'):raise DatasetError('HWP/HWPX originals are excluded')
        if m['type']!='other' and original.suffix.lower().lstrip('.')!=m['type']:raise DatasetError(f'Original extension/type mismatch: {m["id"]}')
        preview=m['preview'];pages=preview['pages']
        if len(pages)!=preview['pageCount']:raise DatasetError(f'Preview pageCount mismatch: {m["id"]}')
        if [p['pageNumber'] for p in pages]!=list(range(1,len(pages)+1)):raise DatasetError(f'Pages must be contiguous and ordered: {m["id"]}')
        if preview['status']=='ready' and not pages:raise DatasetError(f'Ready preview has no pages: {m["id"]}')
        if preview['status']!='ready' and (pages or preview['thumbnail']):raise DatasetError(f'Unavailable/download-only media cannot claim previews: {m["id"]}')
        for page in pages:
            if page['derivedFromMediaId']!=m['id']:raise DatasetError(f'Bad preview parent: {m["id"]}')
            if image_dimensions(file_paths[page['url']])!=(page['width'],page['height']):raise DatasetError(f'Preview dimensions mismatch: {page["url"]}')
        if len({p['url'] for p in pages})!=len(pages):raise DatasetError(f'Duplicate preview page URL: {m["id"]}')
        thumb=preview['thumbnail']
        if thumb:
            if thumb['derivedFromMediaId']!=m['id'] or thumb['pageNumber'] not in [p['pageNumber'] for p in pages]:raise DatasetError(f'Bad thumbnail parent/page: {m["id"]}')
            image_dimensions(file_paths[thumb['url']])
        if m['type'] in ('png','jpg','jpeg','webp'):
            image_dimensions(original)
            if preview['status']=='ready' and len(pages)!=1:raise DatasetError(f'Original image must have exactly one preview: {m["id"]}')
        if m['type']=='pdf' and preview['status']=='ready':
            if not shutil.which('pdfinfo'):raise DatasetError('pdfinfo (Poppler) is required to verify original PDF page completeness')
            result=subprocess.run(['pdfinfo',str(original)],capture_output=True,text=True,timeout=30)
            match=re.search(r'^Pages:\s+(\d+)',result.stdout,re.M)
            if result.returncode or not match or int(match[1])!=len(pages):raise DatasetError(f'PDF page completeness mismatch: {m["id"]}')
            pdf_checks+=1
        if m['type']=='pptx' and preview['status']=='ready':
            with zipfile.ZipFile(original) as z:slides=sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml',n)) for n in z.namelist())
            if slides!=len(pages):raise DatasetError(f'PPTX slide completeness mismatch: {m["id"]}')
        page_total+=len(pages)
    relations=set();used_media=set()
    target_maps={'notice':{nid:notice},'group':indexes['groups'],'building':indexes['buildings'],'unit':indexes['units']}
    for r in data['relations']:
        if r['mediaId'] not in indexes['media']:raise DatasetError(f'Unknown relation mediaId: {r["mediaId"]}')
        if r['targetId'] not in target_maps[r['targetType']]:raise DatasetError(f'Unknown relation target: {r["targetType"]} {r["targetId"]}')
        triple=(r['mediaId'],r['targetType'],r['targetId'],r['role'])
        if triple in relations:raise DatasetError(f'Duplicate media/target/role relationship: {triple}')
        relations.add(triple);used_media.add(r['mediaId'])
        if r['match'] in ('address','location','group') and r['targetType'] not in ('building','group'):raise DatasetError('Address/location/group matches require a building or group target')
        provenance=indexes['media'][r['mediaId']]['provenance']
        if r['sourceAddress']!=provenance['sourceAddress']:raise DatasetError('Relationship sourceAddress differs from media provenance')
        if r['targetType']=='group':
            if r['match'] in ('address','location'):raise DatasetError('Group targets have no single address; use group or explicit match')
            if r['match']=='group' and provenance['groupName']!=indexes['groups'][r['targetId']]['name']:raise DatasetError('Group relationship provenance mismatch')
        if r['targetType']=='building':
            b=indexes['buildings'][r['targetId']];m=indexes['media'][r['mediaId']];provenance=m['provenance']
            if r['match']!='explicit' and provenance['groupName']!=indexes['groups'][b['groupId']]['name']:raise DatasetError('Related brochure belongs to a different group')
            if r['sourceAddress']!=provenance['sourceAddress']:raise DatasetError('Relationship sourceAddress differs from media provenance')
            if r['match']=='address' and norm(r['sourceAddress'])!=norm(b['address']):raise DatasetError('Address match claim does not match target address')
            if r['match']=='location':
                source_location=provenance.get('location')
                if not source_location or not same_location(source_location,b['location']):raise DatasetError('Location match has no matching validated source location')
    if used_media!=set(indexes['media']):raise DatasetError('Every media item must have an explicit relationship')
    return {'schemaVersion':VERSION,'noticeId':nid,'units':len(data['units']),'buildings':len(data['buildings']),'groups':len(data['groups']),'media':len(data['media']),'previewPages':page_total,'relations':len(data['relations']),'files':len(file_paths),'pdfCompletenessChecks':pdf_checks,'fileHashes':file_hashes}

def role_for(name,typ,common=False):
    if common:
        if typ in ('xlsx','xls','csv','tsv'):return 'inventory'
        if re.search(r'q.?n.?a|q\s*&\s*a',name,re.I):return 'qna'
        return 'announcement'
    if '평면' in name:return 'floorplan'
    if '사진' in name:return 'photo'
    return 'brochure'
def norm(x):return re.sub(r'\s+',' ',x).strip()
def same_location(a,b):return bool(a and b and a['status']=='validated' and b['status']=='validated' and abs(a['lat']-b['lat'])<1e-7 and abs(a['lng']-b['lng'])<1e-7)

def import_current(source,geocodes,attachments,asset_root,notice_id,manifest=None,notice_config=None):
    config=(notice_config or {}).get('notice',notice_config or {})
    notice={k:source[k] for k in ('title','sourceUrl','noticeDate','collectedDate')}
    notice.update({'id':notice_id,'regionLabel':'지역','kind':'임대주택','badge':'','appTitle':'주택 지도','providerShort':'공급기관','providerName':'공급기관','description':'주택목록과 첨부자료를 지도에서 확인합니다.','spreadsheet':source.get('spreadsheet',{}),'coordinateAttribution':'원본 주소와 검증된 위치 출처를 확인하세요.'})
    notice.update(config)
    if notice['id']!=notice_id:raise DatasetError('notice-config id does not match --notice-id')
    data={'schemaVersion':VERSION,'notice':notice,'groups':[],'buildings':[],'units':[],'media':[],'relations':[],'extensions':{'housing':source.get('housing',[])}}
    groups={};buildings={}
    for u in source['units']:
        group=u['group'];address=u['address']
        if group not in groups:
            groups[group]=stable(notice_id,'group',group);data['groups'].append({'id':groups[group],'name':group})
        key=(group,address)
        if key not in buildings:
            geo=geocodes.get(address)
            if not geo:raise DatasetError(f'Missing exact original address geocode: {address}')
            buildings[key]=stable(notice_id,'building',group,address)
            data['buildings'].append({'id':buildings[key],'groupId':groups[group],'address':address,'city':address.split()[1] if len(address.split())>1 else address,'location':{'lat':geo['lat'],'lng':geo['lng'],'status':geo['status'],'source':geo['source'],'matchedAddress':geo['matchedAddress']}})
        record=copy.deepcopy(u);original_id=record.pop('id')
        record.update(id=stable(notice_id,'unit',group,address,original_id),buildingId=buildings[key],originalId=original_id)
        if 'rawFields' not in record:raise DatasetError('Source units require rawFields; do not silently synthesize source cells')
        data['units'].append(record)
    records={str(r['id']):r for r in (manifest or {}).get('records',[]) if r.get('path')}
    for r in source['brochures']:records.setdefault(str(r['id']),r)
    common=set(map(str,source['commonFiles']));media_map={}
    for source_id,a in attachments.items():
        source_id=str(source_id);r=records.get(source_id)
        if not r:raise DatasetError(f'Missing original source record for media {source_id}; pass --manifest')
        mid=f'{notice_id}:media:{source_id}';media_map[source_id]=mid
        original=local_file(asset_root,a['url']);sha=digest(original)
        if r.get('sha256') and r['sha256']!=sha:raise DatasetError(f'Source original hash mismatch: {source_id}')
        pages=[]
        for n,url in enumerate(a['pages'],1):
            width,height=image_dimensions(local_file(asset_root,url));pages.append({'pageNumber':n,'url':url,'derivedFromMediaId':mid,'width':width,'height':height})
        thumbnail={'url':a['thumbnail'],'derivedFromMediaId':mid,'pageNumber':1} if a.get('thumbnail') else None
        data['media'].append({'id':mid,'name':a['name'],'type':a['type'],'original':{'url':a['url'],'sourceUrl':r['url'],'sha256':sha,'size':original.stat().st_size},'preview':{'status':a['previewStatus'],'pageCount':a['pageCount'],'pages':pages,'thumbnail':thumbnail},'provenance':{'sourceId':source_id,'kind':r['kind'],'groupName':r.get('housing',''),'sourceAddress':r.get('address',''),'sourceEndpoint':r['source'],**({'location':geocodes[r['address']]} if r.get('address') and r['address'] in geocodes else {})}})
    def relation(source_id,target_type,target_id,role,match,source_address):
        mid=media_map[str(source_id)];data['relations'].append({'id':stable(notice_id,'relation',mid,target_type,target_id,role),'mediaId':mid,'targetType':target_type,'targetId':target_id,'role':role,'match':match,'sourceAddress':source_address})
    for source_id in source['commonFiles']:
        a=attachments[str(source_id)];relation(source_id,'notice',notice_id,role_for(a['name'],a['type'],True),'explicit','')
    for b in data['buildings']:
        group=next(g['name'] for g in data['groups'] if g['id']==b['groupId'])
        for r in source['brochures']:
            if r['housing']!=group:continue
            match='address' if norm(r['address'])==norm(b['address']) else 'location' if same_location(geocodes.get(r['address']),geocodes.get(b['address'])) else 'group'
            relation(str(r['id']),'building',b['id'],role_for(r['name'],attachments[str(r['id'])]['type']),match,r['address'])
    validate(data,asset_root)
    return data

def compile_runtime(data,prefix=''):
    def url(path):return prefix+path
    group_map={g['id']:g for g in data['groups']};media_map={};canonical_media={m['id']:m for m in data['media']}
    for m in data['media']:
        a={'id':m['provenance']['sourceId'],'stableId':m['id'],'name':m['name'],'type':m['type'],'url':url(m['original']['url']),'pages':[url(p['url']) for p in m['preview']['pages']],'thumbnail':url(m['preview']['thumbnail']['url']) if m['preview']['thumbnail'] else None,'pageCount':len(m['preview']['pages']),'previewStatus':m['preview']['status']}
        media_map[m['id']]=a
    units=collections.defaultdict(list)
    for unit in data['units']:
        u=copy.deepcopy(unit);u['stableId']=u.pop('id');u['id']=u['originalId'];units[u['buildingId']].append(u)
    target_rel=collections.defaultdict(list)
    for r in data['relations']:target_rel[(r['targetType'],r['targetId'])].append(r)
    runtime=[]
    for b in data['buildings']:
        rows=units[b['id']];group=group_map[b['groupId']]['name'];candidates=[]
        for r in target_rel[('building',b['id'])]:candidates.append(r)
        for r in target_rel[('group',b['groupId'])]:candidates.append({**r,'match':'group'})
        for u in rows:
            for r in target_rel[('unit',u['stableId'])]:candidates.append(r)
        candidates.sort(key=lambda r:({'explicit':0,'address':0,'location':1,'group':2}[r['match']],media_map[r['mediaId']]['id']))
        seen=set();media=[]
        for r in candidates:
            binding={k:r[k] for k in ('targetType','targetId','match','role','sourceAddress')}
            if r['targetType']=='unit':binding['originalUnitId']=next(u['originalId'] for u in data['units'] if u['id']==r['targetId'])
            if r['mediaId'] in seen:
                next(m for m in media if m['stableId']==r['mediaId'])['bindings'].append(binding);continue
            seen.add(r['mediaId']);m=media_map[r['mediaId']];media.append({**m,'match':r['match'],'role':r['role'],'sourceAddress':r['sourceAddress'],'sourceUrl':canonical_media[r['mediaId']]['original']['sourceUrl'],'bindings':[binding]})
        def minimum(key):return min((u[key] for u in rows if u.get(key) is not None),default=None)
        def maximum(key):return max((u[key] for u in rows if u.get(key) is not None),default=None)
        runtime.append({'id':b['id'],'group':group,'address':b['address'],'city':b['city'],'lat':b['location']['lat'],'lng':b['location']['lng'],'coordinateSource':b['location']['source'],'matchedAddress':b['location']['matchedAddress'],'units':rows,'unitCount':len(rows),'minDeposit':minimum('deposit'),'maxDeposit':maximum('deposit'),'minArea':minimum('area'),'maxArea':maximum('area'),'rooms':sorted({u['rooms'] for u in rows if u.get('rooms') is not None}),'types':sorted({u.get('type','') for u in rows}),'elevator':True if any(u.get('elevator') is True for u in rows) else None if any(u.get('elevator') is None for u in rows) else False,'media':media,'thumbnail':next((m['thumbnail'] for m in media if m['thumbnail']),None)})
    meta=copy.deepcopy(data['notice']);meta.update(noticeId=meta['id'],totalUnits=len(data['units']),totalBuildings=len(data['buildings']),totalGroups=len(data['groups']),commonFiles=[{**media_map[r['mediaId']],'role':r['role']} for r in target_rel[('notice',data['notice']['id'])]])
    return {'meta':meta,'buildings':runtime,'attachments':{a['id']:a for a in media_map.values()},'housing':data.get('extensions',{}).get('housing',[])}

def runtime_bytes(data,prefix=''):
    return ('window.JEONSE_DATA = '+json.dumps(compile_runtime(data,prefix),ensure_ascii=False,separators=(',',':'),allow_nan=False)+';\n').encode()
def audit_report(data,report):
    return {k:v for k,v in report.items() if k!='fileHashes'}|{'mediaMatches':dict(collections.Counter(r['match'] for r in data['relations'])),'sourceMissingAreaIds':[u['originalId'] for u in data['units'] if u['area'] is None],'sourceFieldsPreserved':True}
def atomic_write(path,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def copy_assets(data,asset_root,target,report):
    for url in asset_urls(data):
        src=local_file(asset_root,url);dst=target/url;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        if digest(dst)!=report['fileHashes'][url]:raise DatasetError(f'Asset copy checksum mismatch: {url}')

def build(dataset_path,asset_root,output):
    data=read_json(dataset_path);report=validate(data,asset_root);output=Path(output).resolve()
    if output==PROJECT/'dist':raise DatasetError('Use activate to replace live dist data')
    if output.exists():raise DatasetError('Build output already exists; choose a new output directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'.',dir=output.parent))
    try:
        copy_assets(data,asset_root,stage,report)
        (stage/'data.js').write_bytes(runtime_bytes(data));(stage/'dataset.json').write_bytes(encode_json(data));(stage/'validation-audit.json').write_bytes(encode_json(audit_report(data,report)))
        os.replace(stage,output)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return audit_report(data,report)|{'output':str(output)}

def activate(dataset_path,asset_root,dist=None,state_dir=None,dry_run=False):
    dataset_path=Path(dataset_path).resolve();asset_root=Path(asset_root).resolve()
    data=read_json(dataset_path);report=validate(data,asset_root)
    content_hash=hashlib.sha256(encode_json(data)+encode_json(report['fileHashes'])).hexdigest()
    prefix=f'datasets/{data["notice"]["id"]}/{content_hash[:20]}/'
    if dry_run:return audit_report(data,report)|{'dryRun':True,'assetPrefix':prefix,'contentHash':content_hash}
    dist=Path(dist or PROJECT/'dist').resolve();state_dir=Path(state_dir or PROJECT/'config').resolve()
    dist.mkdir(parents=True,exist_ok=True);state_dir.mkdir(parents=True,exist_ok=True)
    # All copying and runtime compilation finishes before touching active state.
    stage=Path(tempfile.mkdtemp(prefix='.dataset-stage-',dir=dist))
    snapshot=dist/prefix;created_snapshot=False
    try:
        copy_assets(data,asset_root,stage,report)
        (stage/'dataset.json').write_bytes(encode_json(data))
        payload=runtime_bytes(data,prefix)
        audit=audit_report(data,report)|{'contentHash':content_hash,'assetPrefix':prefix}
        config={'schemaVersion':VERSION,'noticeId':data['notice']['id'],'dataset':str(dataset_path),'assetRoot':str(asset_root),'assetPrefix':prefix,'contentHash':content_hash,'activatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if snapshot.exists():
            for url in asset_urls(data):
                if digest(local_file(snapshot,url))!=report['fileHashes'][url]:raise DatasetError('Existing immutable snapshot content differs')
        else:os.replace(stage,snapshot);created_snapshot=True
        # The app reads only data.js: replace that pointer LAST. Roll back every
        # active-state file if a write/rename fails. Previous snapshots stay valid.
        updates=[(state_dir/'active-dataset.json',encode_json(config)),(state_dir/'validation-audit.json',encode_json(audit)),(dist/'data.js',payload)]
        backups={p:p.read_bytes() if p.exists() else None for p,_ in updates}
        try:
            for path,content in updates:atomic_write(path,content)
        except Exception:
            for path,content in reversed(list(backups.items())):
                if content is None:path.unlink(missing_ok=True)
                else:atomic_write(path,content)
            raise
        return audit|{'activeConfig':str(state_dir/'active-dataset.json')}
    except Exception:
        if created_snapshot:shutil.rmtree(snapshot,ignore_errors=True)
        raise
    finally:
        if stage.exists():shutil.rmtree(stage)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import-current',help='Migrate extracted source data; no live changes')
    for option in ('notice-id','source','geocodes','attachments','asset-root','manifest','output'):imp.add_argument('--'+option,required=True)
    imp.add_argument('--notice-config')
    ids=sub.add_parser('ids',help='Generate the canonical stable group/building/unit ID from exact source values')
    ids.add_argument('--notice-id',required=True);ids.add_argument('--kind',required=True,choices=['group','building','unit']);ids.add_argument('--values-json',required=True,help='JSON array: [groupName], [groupName,address], or [groupName,address,originalId]')
    for command in ('validate','build','activate'):
        p=sub.add_parser(command);p.add_argument('--dataset',required=True);p.add_argument('--asset-root',default=str(PROJECT/'dist'))
        if command=='build':p.add_argument('--output',required=True)
        if command=='activate':p.add_argument('--dry-run',action='store_true');p.add_argument('--dist');p.add_argument('--state-dir')
    args=parser.parse_args(argv)
    try:
        if args.command=='ids':
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',args.notice_id) or args.notice_id in ('.','..'):raise DatasetError('Invalid notice id')
            values=json.loads(args.values_json)
            expected={'group':1,'building':2,'unit':3}[args.kind]
            if not isinstance(values,list) or len(values)!=expected:raise DatasetError(f'{args.kind} requires {expected} exact source value(s)')
            if any(not isinstance(v,str) or not v for v in values[:min(2,expected)]):raise DatasetError('Group and address values must be nonempty strings')
            if args.kind=='unit' and (isinstance(values[2],bool) or not isinstance(values[2],(int,str)) or values[2]==''):raise DatasetError('Original unit id must be an integer or nonempty string')
            result={'id':stable(args.notice_id,args.kind,*values)}
        elif args.command=='import-current':
            data=import_current(read_json(args.source),read_json(args.geocodes),read_json(args.attachments),args.asset_root,args.notice_id,read_json(args.manifest),read_json(args.notice_config) if args.notice_config else None)
            atomic_write(args.output,encode_json(data));result={'output':str(Path(args.output).resolve()),**audit_report(data,validate(data,args.asset_root))}
        elif args.command=='validate':
            data=read_json(args.dataset);result=audit_report(data,validate(data,args.asset_root))
        elif args.command=='build':result=build(args.dataset,args.asset_root,args.output)
        else:result=activate(args.dataset,args.asset_root,args.dist,args.state_dir,args.dry_run)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (DatasetError,json.JSONDecodeError,OSError,ValueError,KeyError,subprocess.SubprocessError,zipfile.BadZipFile) as e:
        print('Dataset error: '+str(e),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
