#!/usr/bin/env python3
"""Build each LH notice in a NEW isolated run; never replace an existing project."""
import argparse,datetime,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,uuid,zipfile
from pathlib import Path
from urllib.parse import urlparse,parse_qs,urlencode
from xml.etree import ElementTree as ET

FIELDS={'id':['순번','연번','번호'],'province':['시도'],'supplyRegion':['시군구','공급지역'],'group':['모집단위(주택군)','모집단위','주택군'],'address':['주소','소재지','주택소재지'],'building':['동','동명'],'unit':['호','호수'],'areaBand':['공급형(실사용면적)','공급형'],'area':['실사용면적'],'expandedArea':['확장면적'],'exclusiveArea':['전용면적'],'rooms':['방수','방개수'],'floor':['층수','층'],'elevator':['승강기유무','승강기','엘리베이터'],'type':['주택유형'],'deposit':['임대보증금','보증금'],'notes':['비고']}

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def module(path):
    spec=importlib.util.spec_from_file_location(path.stem,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def infer_spreadsheet(path,ident,adapter):
    with zipfile.ZipFile(path) as z:
        workbook=ET.fromstring(z.read('xl/workbook.xml'));sheets=[s.get('name') for s in workbook.findall('m:sheets/m:sheet',adapter.NS)]
    candidates=[]
    for name in sheets:
        rows=adapter.read_sheet(path,name)
        for n,(raw,_) in rows.items():
            if n>40:continue
            normalized={c:re.sub(r'\s+','',str(v)) for c,v in raw.items()};mapping={};ambiguous=False
            for field,aliases in FIELDS.items():
                hits=[c for c,v in normalized.items() if v in aliases]
                if len(hits)>1:ambiguous=True
                mapping[field]=hits[0] if len(hits)==1 else None
            # Some LH sheets leave the ordinal header blank. Accept only a verified
            # 1..N sequence in the leading A column; do not infer arbitrary IDs.
            if not mapping.get('id') and not normalized.get('A') and mapping.get('address') and mapping.get('group'):
                ordinal=[str(values.get('A','')).strip() for rowno,(values,_) in sorted(rows.items()) if rowno>n and values.get(mapping['address']) and values.get(mapping['group'])]
                if ordinal and ordinal==[str(i) for i in range(1,len(ordinal)+1)]:mapping['id']='A'
            if not ambiguous and all(mapping.get(f) for f in ('id','group','address','deposit')):
                candidates.append({'fileId':str(ident),'sheetName':name,'headerRow':n,'dataStartRow':n+1,'columns':mapping})
    if len(candidates)!=1:raise ValueError('주택목록의 시트·열을 확정할 수 없습니다. --config에 spreadsheet 매핑을 제공하세요.')
    return candidates[0]

def default_runs_dir():
    # 실행 위치(cwd)와 관계없이 모든 공고 빌드를 프로젝트 루트의 lh-runs/에 쌓는다.
    if os.environ.get('LH_RUNS_DIR'):return Path(os.environ['LH_RUNS_DIR'])
    for parent in Path(__file__).resolve().parents:
        if (parent/'AGENTS.md').is_file() and (parent/'start_site.sh').is_file():return parent/'lh-runs'
    return Path('lh-runs')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('url');p.add_argument('--runs-dir',type=Path,default=default_runs_dir(),help='실행 폴더를 쌓는 곳. 기본: LH_RUNS_DIR 또는 프로젝트 루트의 lh-runs/(start_site.sh가 찾는 위치)')
    p.add_argument('--notice-id',help='브라우저에서 확인한 panId. URL 값과 다르면 중단')
    p.add_argument('--html',type=Path,help='브라우저에서 저장한 해당 공고 HTML')
    p.add_argument('--config',type=Path,help='선택: 공고 메타데이터·spreadsheet 매핑·groupAliases')
    p.add_argument('--from-bundle',type=Path,help='이미 검증할 표준 패키지. URL의 공고 ID와 반드시 일치')
    p.add_argument('--reuse-downloads',type=Path,help='같은 URL의 기존 원본 폴더를 읽기 전용 입력으로 복사')
    p.add_argument('--reuse-assets',type=Path,help='같은 원본의 미리보기 assets 폴더. 해시/페이지 검증 필수')
    p.add_argument('--geocodes',type=Path,help='이미 확인한 주소 좌표 명세 복사. 재검증 후 사용')
    p.add_argument('--no-install',action='store_true');p.add_argument('--template',type=Path)
    args=p.parse_args();u=urlparse(args.url)
    if u.scheme!='https' or u.hostname!='apply.lh.or.kr' or u.path!='/lhapply/apply/wt/wrtanc/selectWrtancInfo.do':p.error('LH 공고 상세 HTTPS URL을 입력하세요.')
    ids=parse_qs(u.query).get('panId',[])
    if len(ids)>1:p.error('panId가 중복되었습니다.')
    if ids and args.notice_id and ids[0]!=args.notice_id:p.error('URL panId와 --notice-id가 다릅니다.')
    ident=ids[0] if ids else args.notice_id
    if ident and not re.fullmatch('[0-9]+',ident):p.error('panId는 숫자여야 합니다.')
    template=args.template or Path(__file__).resolve().parents[1]/'assets/template'
    if not template.exists():template=Path(__file__).resolve().parents[1]/'.agents/skills/lh-notice-map/assets/template'
    if not template.is_dir():p.error('깨끗한 스킬 템플릿이 없습니다. --template을 지정하세요.')
    base=args.runs_dir.resolve();base.mkdir(parents=True,exist_ok=True)
    run=base/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+(ident or 'unresolved')+'-'+uuid.uuid4().hex[:8]);run.mkdir()
    for d in ['docs','scripts','config','data','site','reports','tmp']:(run/d).mkdir()
    report={'status':'started','inputUrl':args.url,'noticeId':ident,'runRoot':str(run),'steps':[]}
    write(run/'reports/run.json',report);print('RUN_ROOT='+str(run),flush=True)
    env=os.environ.copy()
    def step(name,command):
        log=run/'reports'/(str(len(report['steps'])+1).zfill(2)+'-'+name+'.log')
        with log.open('w',encoding='utf-8') as f:result=subprocess.run([str(x) for x in command],cwd=run,env=env,stdout=f,stderr=subprocess.STDOUT)
        report['steps'].append({'name':name,'exitCode':result.returncode,'log':str(log.relative_to(run))});write(run/'reports/run.json',report)
        if result.returncode:raise RuntimeError(f'{name} 실패: {log}')
    try:
        if not ident:
            report.update(status='needs_browser',reason='이 URL에는 panId가 없습니다. 열린 공고의 URL/HTML에서 실제 ID를 확인해야 합니다. 이전 공고나 최신 공고로 추측하지 않습니다.')
            write(run/'reports/run.json',report);print(report['reason']);return 2
        params=parse_qs(u.query);params['panId']=[ident]
        url=u._replace(query=urlencode(params,doseq=True)).geturl();report['resolvedUrl']=url
        # Copy only allowlisted implementation resources, never .git, hosting identity or data.js.
        for d in ['scripts','data/schema','site/dist','backend']:shutil.copytree(template/d,run/d,dirs_exist_ok=True)
        references=template.parents[1]/'references'
        if references.exists():
            for name in ['DATA_STANDARD.md','DATA_GUIDE.md']:
                if (references/name).exists():shutil.copy2(references/name,run/'docs'/name)
        missing=[package for package in (['jsonschema'] if args.from_bundle else ['requests','bs4','PIL','jsonschema']) if importlib.util.find_spec(package) is None]
        if missing:
            if args.no_install:raise RuntimeError('필요 Python 패키지: '+','.join(missing))
            deps=run/'tmp/python-deps';step('dependencies',[sys.executable,'-m','pip','install','--target',deps,'requests','beautifulsoup4','Pillow','jsonschema'])
            env['PYTHONPATH']=str(deps)+os.pathsep+env.get('PYTHONPATH','');sys.path.insert(0,str(deps))
        for binary in ['pdfinfo']+([] if args.from_bundle or args.reuse_assets else ['pdftoppm','libreoffice']):
            if not shutil.which(binary):raise RuntimeError('필수 실행 파일 없음: '+binary)
        bundle=run/'data/datasets'/ident;dataset=bundle/'dataset.json'
        if args.from_bundle:
            original=load(args.from_bundle/'dataset.json')
            if original['notice']['id']!=ident:raise ValueError('입력 패키지 공고 ID와 URL이 다릅니다.')
            bundle.mkdir(parents=True);shutil.copy2(args.from_bundle/'dataset.json',dataset)
            ds=module(run/'scripts/dataset.py');ds.validate(original,args.from_bundle)
            for relative in ds.asset_urls(original):
                target=bundle/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ds.local_file(args.from_bundle,relative),target)
        else:
            raw=run/'data/notices'/('lh_'+ident);intermediate=run/'data/intermediate'/ident;intermediate.mkdir(parents=True)
            env.update(LH_PAN_ID=ident,LH_OUTPUT_ROOT=str(raw),LH_NOTICE_URL=url,LH_SOURCE_ROOT=str(raw),LH_ASSETS_DIR=str(bundle/'assets'),LH_TEMP_ROOT=str(run/'tmp/previews'),LH_SOURCE_DATA=str(intermediate/'source-data.json'),LH_MANIFEST=str(raw/'manifest.json'),LH_GEOCODES_OUTPUT=str(intermediate/'geocodes.json'),LH_GEOCODE_CACHE=str(run/'tmp/geocode-cache'))
            if args.reuse_downloads:
                source_manifest=load(args.reuse_downloads/'manifest.json')
                if parse_qs(urlparse(source_manifest['url']).query).get('panId')!=[ident]:raise ValueError('재사용할 원본의 공고 ID가 다릅니다.')
                raw.mkdir(parents=True)
                shutil.copy2(args.reuse_downloads/'manifest.json',raw/'manifest.json')
                if (args.reuse_downloads/'popup_raw.json').exists():shutil.copy2(args.reuse_downloads/'popup_raw.json',raw/'popup_raw.json')
                ds=module(run/'scripts/dataset.py')
                for record in source_manifest['records']:
                    if not record.get('path'):continue
                    if Path(record['path']).suffix.lower() in ('.hwp','.hwpx'):raise ValueError('HWP 입력은 제외해야 합니다.')
                    relative=Path(record['path'])
                    if relative.is_absolute() or '..' in relative.parts:raise ValueError('원본 경로가 안전하지 않습니다.')
                    source=(args.reuse_downloads/relative).resolve()
                    if not source.is_relative_to(args.reuse_downloads.resolve()) or not source.is_file():raise ValueError('원본 파일 경로 이탈 또는 누락')
                    if ds.digest(source)!=record['sha256']:raise ValueError('원본 파일 해시 불일치')
                    dest=raw/record['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            else:
                html=run/'data/notice.html'
                if args.html:shutil.copy2(args.html,html)
                else:
                    import requests
                    response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=40);response.raise_for_status();html.write_text(response.content.decode('utf-8'),encoding='utf-8')
                text=html.read_text(encoding='utf-8')
                if 'fileDownLoad' not in text or 'bbs_ViewA' not in text:
                    report['status']='needs_browser';raise ValueError('직접 접근으로 공고를 읽지 못했습니다. 브라우저로 같은 공고를 열고 HTML을 저장하여 --html과 --notice-id로 재실행하세요.')
                # Browser HTML must identify this notice, not merely an unrelated attachment page.
                found=set(re.findall(r'panId[\s\W]{1,12}([0-9]{10,})',text))
                if found and ident not in found:raise ValueError('저장된 HTML에 지정 공고 ID가 없습니다.')
                env['LH_NOTICE_HTML']=str(html);step('collect',[sys.executable,run/'scripts/collect_lh.py'])
            manifest=load(raw/'manifest.json');custom=load(args.config) if args.config else {}
            xlsx=[record for record in manifest['records'] if record.get('path') and Path(record['path']).suffix.lower()=='.xlsx' and '주택목록' in re.sub(r'\s+','',record['name'])]
            if custom.get('spreadsheet',{}).get('fileId'):xlsx=[record for record in manifest['records'] if record.get('path') and str(record['id'])==str(custom['spreadsheet']['fileId'])]
            if len(xlsx)!=1:raise ValueError('기준 주택목록 XLSX가 하나로 확정되지 않습니다. --config에 spreadsheet.fileId를 지정하세요.')
            record=xlsx[0];xlsx_path=raw/record['path'];adapter=module(run/'scripts/import_xlsx.py')
            spec=custom.get('spreadsheet') or infer_spreadsheet(xlsx_path,record['id'],adapter)
            rows=adapter.read_sheet(xlsx_path,spec['sheetName']);dates=set(re.findall(r'(20\d\d)[.\-/](\d{2})[.\-/](\d{2})',' '.join(str(v) for n,(values,_) in rows.items() if n<spec['headerRow'] for v in values.values())))
            date=custom.get('notice',{}).get('noticeDate')
            if not date:
                if len(dates)!=1:raise ValueError('기준일을 확정할 수 없습니다. --config의 notice.noticeDate를 원문 기준으로 지정하세요.')
                date='-'.join(next(iter(dates)))
            notice={'id':ident,'title':manifest['title'],'sourceUrl':url,'noticeDate':date,'collectedDate':datetime.date.today().isoformat(),'appTitle':'LH 주택 지도','providerShort':'LH','providerName':'LH청약플러스','regionLabel':'모집지역','kind':'임대주택','badge':'정정공고' if '정정' in manifest['title'] else ''}
            notice.update(custom.get('notice',{}))
            if notice['id']!=ident or parse_qs(urlparse(notice['sourceUrl']).query).get('panId')!=[ident]:raise ValueError('설정과 입력 URL의 공고 ID가 다릅니다.')
            config={'notice':notice,'spreadsheet':spec,'groupAliases':custom.get('groupAliases',{}),'paths':{'xlsx':str(xlsx_path),'manifest':str(raw/'manifest.json'),'geocodes':str(intermediate/'geocodes.json'),'attachments':str(bundle/'assets/attachments.json'),'assetRoot':str(bundle)}}
            config_file=run/'config/notice.json';write(config_file,config)
            step('extract',[sys.executable,run/'scripts/import_xlsx.py','--config',config_file,'--output',dataset,'--extract-only',intermediate/'source-data.json'])
            if args.reuse_assets:shutil.copytree(args.reuse_assets,bundle/'assets')
            else:step('previews',[sys.executable,run/'scripts/prepare_site_assets.py'])
            if args.geocodes:shutil.copy2(args.geocodes,intermediate/'geocodes.json')
            else:step('geocodes',[sys.executable,run/'scripts/geocode_addresses.py'])
            geo=load(intermediate/'geocodes.json');source=load(intermediate/'source-data.json')
            unresolved=[u['address'] for u in source['units'] if geo.get(u['address'],{}).get('status')!='validated']
            if unresolved:write(run/'reports/unresolved-addresses.json',list(dict.fromkeys(unresolved)));raise ValueError('미확정 주소가 있습니다. 임의 좌표로 빌드하지 않습니다.')
            step('import',[sys.executable,run/'scripts/import_xlsx.py','--config',config_file,'--output',dataset])
            step('inventory',[sys.executable,run/'scripts/build_inventory.py','--root',raw,'--output',raw/'첨부파일정리.xlsx'])
            with zipfile.ZipFile(run/'reports/첨부파일.zip','x',zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(raw.rglob('*')):
                    if path.is_file():archive.write(path,path.relative_to(raw))
        step('validate',[sys.executable,run/'scripts/dataset.py','validate','--dataset',dataset,'--asset-root',bundle])
        step('activate',[sys.executable,run/'scripts/dataset.py','activate','--dataset',dataset,'--asset-root',bundle,'--dist',run/'site/dist','--state-dir',run/'config'])
        if not (run/'site/dist/competition-config.json').is_file():raise RuntimeError('competition-config.json was not generated')
        report.update(status='complete',siteDirectory='site/dist',dataset=str(dataset.relative_to(run)),validation=load(run/'config/validation-audit.json'))
        (run/'docs/RUN.md').write_text('실행별 새 폴더입니다. 기존 프로젝트를 수정하지 않습니다.\n\n로컬 실행(지도 + 경쟁률 백엔드, Python 표준 라이브러리): 작업공간에서 ./start_site.sh 후 이 실행을 선택하거나, 이 폴더에서 python backend/server.py --directory site/dist --state-dir tmp/competition --port 8765\n\n경쟁률 소스 URL: site/dist/competition-config.json의 sourceUrl(데이터셋 notice.sourceUrl에서 생성). 백엔드가 30분마다 조회해 /api/competition으로 제공하고, 화면의 \'지금 새로고침\'은 POST /api/competition/refresh로 즉시 조회합니다.\n\n호스팅은 새 Sites 프로젝트를 생성하고 이 실행 폴더에 새 ID를 저장해 진행합니다.\n',encoding='utf-8')
        print('COMPLETE='+str(run/'site/dist'),flush=True);return 0
    except Exception as e:
        if report['status']!='needs_browser':report['status']='failed'
        report['error']=str(e);print(str(e),file=sys.stderr);return 2 if report['status']=='needs_browser' else 1
    finally:write(run/'reports/run.json',report)

if __name__=='__main__':raise SystemExit(main())
