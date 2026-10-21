#!/usr/bin/env python3
"""Copy original attachments and render browser-friendly previews; never modify inputs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import collections,json,re,shutil,subprocess,tempfile,os
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[1]
PAN_ID=os.environ.get('LH_PAN_ID','2015122300020927')
SOURCE=Path(os.environ.get('LH_SOURCE_ROOT',str(ROOT/'data/notices'/('lh_'+PAN_ID))))
ASSETS=Path(os.environ.get('LH_ASSETS_DIR',str(ROOT/'data/datasets'/PAN_ID/'assets')))
TMP=Path(os.environ.get('LH_TEMP_ROOT',str(ROOT/'tmp/previews'/PAN_ID)))
for p in [ASSETS/'files',ASSETS/'previews',TMP]: p.mkdir(parents=True,exist_ok=True)
manifest=json.loads((SOURCE/'manifest.json').read_text())
records=[r for r in manifest['records'] if r.get('path')]

def render_pdf(pdf,ident):
    d=ASSETS/'previews'/ident; d.mkdir(parents=True,exist_ok=True)
    info=subprocess.run(['pdfinfo',str(pdf)],capture_output=True,text=True,check=True).stdout
    count=int(re.search(r'^Pages:\s*(\d+)',info,re.M).group(1))
    existing=list(d.glob('page-*.webp'))
    if len(existing)==count and (d/'thumb.webp').exists():
        return [f'assets/previews/{ident}/page-{i:03d}.webp' for i in range(1,count+1)],f'assets/previews/{ident}/thumb.webp',count
    with tempfile.TemporaryDirectory(dir=TMP,prefix=ident+'-') as t:
        prefix=Path(t)/'page'
        subprocess.run(['pdftoppm','-jpeg','-jpegopt','quality=90','-scale-to','1600',str(pdf),str(prefix)],check=True,capture_output=True)
        pages=sorted(Path(t).glob('page-*.jpg'),key=lambda p:int(p.stem.split('-')[-1]))
        if len(pages)!=count: raise RuntimeError(f'Expected {count} pages, got {len(pages)}')
        for i,p in enumerate(pages,1):
            with Image.open(p) as im:
                im.convert('RGB').save(d/f'page-{i:03d}.webp','WEBP',quality=82,method=4)
                if i==1:
                    thumb=im.convert('RGB'); thumb.thumbnail((480,680)); thumb.save(d/'thumb.webp','WEBP',quality=82,method=4)
    return [f'assets/previews/{ident}/page-{i:03d}.webp' for i in range(1,count+1)],f'assets/previews/{ident}/thumb.webp',count

def process(r):
    ident=str(r['id']); src=SOURCE/r['path']; ext=src.suffix.lower().lstrip('.')
    if ext in ('hwp','hwpx'): raise RuntimeError('HWP explicitly excluded')
    dest=ASSETS/'files'/f'{ident}.{ext}'; shutil.copy2(src,dest)
    result={'id':ident,'name':r['name'],'type':ext,'url':f'assets/files/{ident}.{ext}','pages':[],'thumbnail':None,'pageCount':0,'previewStatus':'download-only'}
    if ext=='pdf':
        result['pages'],result['thumbnail'],result['pageCount']=render_pdf(src,ident)
        result['previewStatus']='ready'
    elif ext in ('png','jpg','jpeg'):
        d=ASSETS/'previews'/ident; d.mkdir(parents=True,exist_ok=True)
        with Image.open(src) as original:
            im=ImageOps.exif_transpose(original).convert('RGB'); im.thumbnail((1600,1600)); im.save(d/'page-001.webp','WEBP',quality=86,method=4)
            im.thumbnail((480,680)); im.save(d/'thumb.webp','WEBP',quality=82,method=4)
        result.update(pages=[f'assets/previews/{ident}/page-001.webp'],thumbnail=f'assets/previews/{ident}/thumb.webp',pageCount=1,previewStatus='ready')
    elif ext=='pptx':
        out=TMP/ident; out.mkdir(parents=True,exist_ok=True)
        pdf=out/(src.stem+'.pdf')
        if not pdf.exists(): subprocess.run(['libreoffice','-env:UserInstallation=file://'+str(TMP/'lo_profile'),'--headless','--convert-to','pdf','--outdir',str(out),str(src)],check=True,capture_output=True,timeout=120)
        if not pdf.exists(): raise RuntimeError('PowerPoint PDF conversion failed')
        result['pages'],result['thumbnail'],result['pageCount']=render_pdf(pdf,ident); result['previewStatus']='ready'
    return ident,result

results={}; errors=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    tasks={pool.submit(process,r):r for r in records}
    for f in as_completed(tasks):
        r=tasks[f]
        try:
            ident,result=f.result(); results[ident]=result
            print(f'{ident} {result["type"]}: {result["pageCount"]} pages',flush=True)
        except Exception as e: errors.append({'id':r['id'],'error':str(e)}); print('ERROR',r['id'],str(e),flush=True)
results={str(r['id']):results[str(r['id'])] for r in records if str(r['id']) in results}
(ASSETS/'attachments.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
summary={'attachments':len(results),'types':dict(collections.Counter(r['type'] for r in results.values())),'previewPages':sum(r['pageCount'] for r in results.values()),'bytes':sum(p.stat().st_size for p in ASSETS.rglob('*') if p.is_file()),'errors':errors}
(TMP/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
if errors: raise SystemExit(1)
