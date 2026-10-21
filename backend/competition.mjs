// Shared by the local Node server and the hosted Worker. No browser-side scraping.
export const INTERVAL_MS=30*60*1000;
export const RETRY_MS=5*60*1000;
const clean=s=>String(s).replace(/<[^>]*>/g,' ').replace(/&(?:nbsp|amp|lt|gt|quot|#39);/g,x=>({'&nbsp;':' ','&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'"}[x])).replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n))).replace(/\s+/g,' ').trim();
export const groupKey=s=>String(s).normalize('NFC').replace(/\s+/g,'').trim();
function count(text){const value=clean(text);if(value===''||['-','—','미공개'].includes(value))return null;if(!/^\d[\d,]*$/.test(value))throw Error('신청 현황 숫자 형식이 바뀌었습니다.');const number=Number(value.replaceAll(',',''));if(!Number.isSafeInteger(number)||number<0)throw Error('잘못된 신청 현황 수치입니다.');return number;}
export function sourceFor(meta){const url=new URL(meta.sourceUrl);if(url.protocol!=='https:'||url.hostname!=='apply.lh.or.kr'||url.pathname!=='/lhapply/apply/wt/wrtanc/selectWrtancInfo.do'||url.username||url.password)throw Error('지원하지 않는 LH 원문 URL입니다.');const ids=url.searchParams.getAll('panId');if(ids.length!==1||ids[0]!==String(meta.id||meta.noticeId)||!/^\d+$/.test(ids[0]))throw Error('데이터와 원문 공고 ID가 다릅니다.');return url.href;}
export function parseCompetition(html,meta){
 const sourceUrl=sourceFor(meta),nid=String(meta.id||meta.noticeId);
 const notice=html.match(/<input\b(?=[^>]*\bname\s*=\s*["']panId["'])(?=[^>]*\bvalue\s*=\s*["']([^"']+)["'])[^>]*>/i);
 if(!notice||notice[1]!==nid)throw Error('응답이 요청한 LH 공고와 일치하지 않습니다.');
 const table=html.match(/<table\b[^>]*\bid\s*=\s*["']htyListTb08["'][^>]*>([\s\S]*?)<\/table>/i);
 if(!table)throw Error('지원하는 신청 현황 표가 없습니다. 원문 구조 또는 공개 여부를 확인하세요.');
 const headers=table[1].match(/<thead\b[^>]*>([\s\S]*?)<\/thead>/i)?.[1]||'';
 for(const label of ['공급호수','모집인원','신청건수'])if(!clean(headers).includes(label))throw Error('신청 현황 표의 열 구성이 바뀌었습니다.');
 const totalsRow=[...headers.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)].map(x=>x[1]).find(x=>clean(x).startsWith('합계'));
 const totalCells=totalsRow?[...totalsRow.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi)].map(x=>clean(x[1])):[];
 const body=table[1].match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/i)?.[1];if(!body)throw Error('신청 현황 행이 없습니다.');
 const rows=[];
 for(const match of body.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)){
  const cells={};for(const c of match[1].matchAll(/<td\b[^>]*\bdata-th-code\s*=\s*["'](\d+)["'][^>]*>([\s\S]*?)<\/td>/gi))cells[c[1]]=clean(c[2]);
  if(!cells['1'])continue;
  if(!['2','3','4'].every(k=>k in cells))throw Error('일부 신청 현황 행의 열이 누락되었습니다.');
  rows.push({groupName:cells['1'],supply:count(cells['2']),recruitment:count(cells['3']),applications:count(cells['4'])});
 }
 if(!rows.length)throw Error('주택군 신청 현황이 비어 있습니다.');
 const groups=new Map();
 for(const row of rows){const key=groupKey(row.groupName);if(!groups.has(key))groups.set(key,{groupName:row.groupName,key,supply:0,recruitment:0,applications:0,sourceRowCount:0});const g=groups.get(key);for(const k of ['supply','recruitment','applications'])g[k]=g[k]===null||row[k]===null?null:g[k]+row[k];g.sourceRowCount++;}
 const list=[...groups.values()].map(g=>({...g,supplyRatio:g.applications!==null&&g.supply>0?g.applications/g.supply:null,recruitmentRatio:g.applications!==null&&g.recruitment>0?g.applications/g.recruitment:null}));
 const totals={};for(const k of ['supply','recruitment','applications'])totals[k]=list.some(g=>g[k]===null)?null:list.reduce((s,g)=>s+g[k],0);
 if(totalCells.length!==4)throw Error('공급정보 합계 행을 확인할 수 없습니다.');
 for(const [i,k] of ['supply','recruitment','applications'].entries())if(count(totalCells[i+1])!==totals[k])throw Error('신청 현황 합계가 개별 행과 다릅니다.');
 if(Array.isArray(meta.expectedGroups)){const actual=new Set(list.map(g=>g.key));const expected=new Set(meta.expectedGroups.map(groupKey));if(actual.size!==expected.size||[...expected].some(k=>!actual.has(k)))throw Error('원문 주택군과 이 사이트의 데이터셋이 다릅니다. 정정공고라면 스킬로 새 사이트를 추가하세요.');}
 if(Number.isSafeInteger(meta.totalUnits)&&meta.totalUnits!==totals.supply)throw Error('원문 공급호수가 현재 주택목록과 다릅니다. 정정 자료를 확인하세요.');
 return {noticeId:nid,sourceUrl,scope:'housing-group',groups:list,sourceRowCount:rows.length,totals:{...totals,supplyRatio:totals.applications!==null&&totals.supply>0?totals.applications/totals.supply:null,recruitmentRatio:totals.applications!==null&&totals.recruitment>0?totals.applications/totals.recruitment:null}};
}
export class CompetitionService{
 constructor({meta,store,fetcher=fetch,now=()=>Date.now()}){this.meta=meta;this.url=sourceFor(meta);this.store=store;this.fetcher=fetcher;this.now=now;this.pending=null;}
 async read(){const record=await this.store.read(this.meta.id||this.meta.noticeId);return this.view(record);}
 view(record){const payload=record?.payload?JSON.parse(record.payload):null,lastSuccess=record?.last_success||null;return {schemaVersion:'1.0.0',noticeId:String(this.meta.id||this.meta.noticeId),sourceUrl:this.url,intervalMinutes:30,status:payload?(record.last_error?'stale-error':this.now()-lastSuccess>=INTERVAL_MS?'stale':'ok'):(record?.last_error?'unavailable':'pending'),lastSuccessAt:lastSuccess?new Date(lastSuccess).toISOString():null,lastAttemptAt:record?.last_attempt?new Date(record.last_attempt).toISOString():null,nextRefreshAt:lastSuccess?new Date(lastSuccess+INTERVAL_MS).toISOString():null,lastError:record?.last_error||null,data:payload};}
 async refresh({force=false}={}){
  if(this.pending)return this.pending;
  this.pending=this.perform(force);try{return await this.pending;}finally{this.pending=null;}
 }
 async perform(force){
  const id=String(this.meta.id||this.meta.noticeId),time=this.now(),prior=await this.store.read(id);
  if(!force&&prior?.last_success&&time-prior.last_success<INTERVAL_MS)return this.view(prior);
  // Failed lookups back off so polling clients cannot hammer the LH source.
  if(!force&&prior?.last_error&&time-(prior.last_attempt||0)<RETRY_MS)return this.view(prior);
  const token=crypto.randomUUID();if(!await this.store.acquire(id,time,token))return {...this.view(await this.store.read(id)),refreshing:true};
  try{
   const response=await this.fetcher(this.url,{headers:{'User-Agent':'LHNoticeMap/1.0','Accept':'text/html','Cache-Control':'no-cache'},redirect:'error',signal:AbortSignal.timeout(25000)});
   if(!response.ok)throw Error('LH 원문 응답 HTTP '+response.status);
   const bytes=await response.arrayBuffer();if(bytes.byteLength>4*1024*1024)throw Error('LH 응답 크기가 예상 범위를 초과했습니다.');
   const parsed=parseCompetition(new TextDecoder('utf-8',{fatal:true}).decode(bytes),this.meta);
   await this.store.save(id,token,JSON.stringify(parsed),this.now());
  }catch(e){const message=e.name==='TimeoutError'?'LH 원문 조회 시간 초과':String(e.message||e).slice(0,220);await this.store.fail(id,token,this.now(),message);}
  return this.view(await this.store.read(id));
 }
}
export const CACHE_SCHEMA=`CREATE TABLE IF NOT EXISTS competition_cache (notice_id TEXT PRIMARY KEY,payload TEXT,last_success INTEGER,last_attempt INTEGER,last_error TEXT,lock_until INTEGER NOT NULL DEFAULT 0,lock_token TEXT)`;
export function sqlStore(db){return {
 async read(id){return db.prepare('SELECT * FROM competition_cache WHERE notice_id=?').bind(id).first();},
 async acquire(id,time,token){await db.prepare('INSERT OR IGNORE INTO competition_cache(notice_id) VALUES (?)').bind(id).run();return !!await db.prepare('UPDATE competition_cache SET lock_until=?,lock_token=?,last_attempt=? WHERE notice_id=? AND lock_until<=? RETURNING notice_id').bind(time+45000,token,time,id,time).first();},
 async save(id,token,payload,time){await db.prepare('UPDATE competition_cache SET payload=?,last_success=?,last_attempt=?,last_error=NULL,lock_until=0,lock_token=NULL WHERE notice_id=? AND lock_token=?').bind(payload,time,time,id,token).run();},
 async fail(id,token,time,message){await db.prepare('UPDATE competition_cache SET last_attempt=?,last_error=?,lock_until=0,lock_token=NULL WHERE notice_id=? AND lock_token=?').bind(time,message,id,token).run();}
};}
export async function api(request,service){
 const url=new URL(request.url);if(url.pathname!=='/api/competition'&&url.pathname!=='/api/competition/refresh')return null;
 const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'};
 if(request.method==='GET'&&url.pathname==='/api/competition'){// Hosted Workers have no timer: a GET past the 30-minute window refreshes lazily.
 let result=await service.read();if(result.status!=='ok')result=await service.refresh();return new Response(JSON.stringify(result),{headers});}
 if(request.method!=='POST'||url.pathname!=='/api/competition/refresh')return new Response(JSON.stringify({error:'Method not allowed'}),{status:405,headers:{...headers,Allow:url.pathname.endsWith('/refresh')?'POST':'GET'}});
 const origin=request.headers.get('Origin');if(origin&&origin!==url.origin)return new Response(JSON.stringify({error:'Origin not allowed'}),{status:403,headers});
 // User refresh bypasses the 30-minute freshness cache. Concurrent requests share one in-flight lookup.
 const result=await service.refresh({force:true});return new Response(JSON.stringify(result),{status:result.status==='unavailable'?502:200,headers});
}
