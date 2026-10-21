import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCompetition,CompetitionService,INTERVAL_MS,RETRY_MS,api} from '../backend/competition.mjs';

const fixture=readFileSync(new URL('./fixtures/lh_competition_2015122300020927.html',import.meta.url),'utf8');
const meta=JSON.parse(readFileSync(new URL('../public/competition-config.json',import.meta.url),'utf8'));

function memoryStore(){
 const rows=new Map();
 return {rows,
  async read(id){return rows.get(id)||null;},
  async acquire(id,time,token){const r=rows.get(id)||{notice_id:id,lock_until:0};if(r.lock_until>time)return false;rows.set(id,{...r,lock_until:time+45000,lock_token:token,last_attempt:time});return true;},
  async save(id,token,payload,time){const r=rows.get(id);if(r.lock_token===token)rows.set(id,{...r,payload,last_success:time,last_attempt:time,last_error:null,lock_until:0,lock_token:null});},
  async fail(id,token,time,message){const r=rows.get(id);if(r.lock_token===token)rows.set(id,{...r,last_attempt:time,last_error:message,lock_until:0,lock_token:null});}};
}
const ok=html=>async()=>new Response(html,{status:200});

test('parses the LH supply table and verifies totals',()=>{
 const p=parseCompetition(fixture,meta);
 assert.equal(p.groups.length,meta.expectedGroups.length);
 assert.deepEqual([p.totals.supply,p.totals.recruitment,p.totals.applications],[344,835,5222]);
 const g=p.groups.find(x=>x.groupName==='수원고색(디케이타워)');
 assert.deepEqual([g.supply,g.recruitment,g.applications,g.supplyRatio],[3,10,102,34]);
 // Rows repeated for one housing group are summed, never dropped.
 assert.ok(p.sourceRowCount>=p.groups.length);
});

test('rejects a response for another notice or a changed dataset',()=>{
 assert.throws(()=>parseCompetition(fixture.replace('2015122300020927','2015122300099999'),meta),/일치하지/);
 assert.throws(()=>parseCompetition(fixture,{...meta,totalUnits:343}),/공급호수/);
 assert.throws(()=>parseCompetition(fixture,{...meta,expectedGroups:meta.expectedGroups.slice(1)}),/주택군/);
 assert.throws(()=>parseCompetition(fixture.replace('htyListTb08','other'),meta),/신청 현황 표/);
 assert.throws(()=>parseCompetition(fixture,{...meta,sourceUrl:'https://example.com/?panId='+meta.id}),/URL/);
});

test('unpublished counts stay null instead of becoming 0:1',()=>{
 const html=fixture.replace(/(<td data-th-code="4">)[^<]*(<\/td>)/,'$1-$2');
 assert.throws(()=>parseCompetition(html,meta),/합계/);// totals row no longer matches the null group
});

test('fresh cache is reused, stale cache refetches, user refresh forces',async()=>{
 let now=1_000_000,calls=0;const store=memoryStore();
 const service=new CompetitionService({meta,store,fetcher:async()=>{calls++;return ok(fixture)();},now:()=>now});
 assert.equal((await service.refresh()).status,'ok');assert.equal(calls,1);
 now+=60_000;assert.equal((await service.refresh()).status,'ok');assert.equal(calls,1);
 assert.equal((await service.refresh({force:true})).status,'ok');assert.equal(calls,2);
 now+=INTERVAL_MS;assert.equal((await service.read()).status,'stale');
 const res=await api(new Request('http://x/api/competition'),service);
 assert.equal((await res.json()).status,'ok');assert.equal(calls,3);
});

test('failure keeps the last good data and backs off',async()=>{
 let now=1_000_000,fail=false,calls=0;const store=memoryStore();
 const service=new CompetitionService({meta,store,fetcher:async()=>{calls++;return fail?new Response('x',{status:503}):new Response(fixture);},now:()=>now});
 await service.refresh();fail=true;now+=INTERVAL_MS;
 const view=await service.refresh();
 assert.equal(view.status,'stale-error');assert.match(view.lastError,/503/);assert.equal(view.data.totals.applications,5222);
 now+=RETRY_MS-1;await service.refresh();assert.equal(calls,2);
 now+=1;await service.refresh();assert.equal(calls,3);
});

test('refresh endpoint is POST-only and same-origin',async()=>{
 const service=new CompetitionService({meta,store:memoryStore(),fetcher:ok(fixture)});
 assert.equal((await api(new Request('http://x/api/competition/refresh'),service)).status,405);
 assert.equal((await api(new Request('http://x/api/competition/refresh',{method:'POST',headers:{Origin:'http://evil'}}),service)).status,403);
 assert.equal((await api(new Request('http://x/api/competition/refresh',{method:'POST',headers:{Origin:'http://x'}}),service)).status,200);
 assert.equal(await api(new Request('http://x/other'),service),null);
});
