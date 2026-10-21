(() => {
'use strict';
const D=window.JEONSE_DATA,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const icons={map:'<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/>',table:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10M15 10v10"/>',bookmark:'<path d="M6 4h12v17l-6-4-6 4V4Z"/>',file:'<path d="M14 3H5v18h14V8l-5-5Z"/><path d="M14 3v6h5M8 13h8M8 17h6"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',reset:'<path d="M4 5v6h6M4 11a8 8 0 1 1 1.8 7"/>',expand:'<path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/>',label:'<path d="M3 5h18v13H8l-5 3V5Z"/><path d="M7 9h10M7 13h7"/>',download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',house:'<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8"/>',elevator:'<rect x="4" y="2" width="16" height="20" rx="2"/><path d="m8 9 4-4 4 4m-8 6 4 4 4-4"/>',image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>'};
const svg=(name,fill=false)=>`<svg viewBox="0 0 24 24" fill="${fill?'currentColor':'none'}" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]||icons.house}</svg>`;
function hydrate(scope=document){scope.querySelectorAll('[data-icon]').forEach(e=>e.innerHTML=svg(e.dataset.icon));}
hydrate();
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=n=>n==null?'—':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2}).format(n);
function money(n){if(n==null)return '—';const e=Math.floor(n/1e8),m=Math.round((n%1e8)/1e4);return e?(e+'억'+(m?' '+num(m)+'만':'')):(num(Math.round(n/1e4))+'만');}
function priceRange(a,b){return a===b?money(a):`${money(a)} ~ ${money(b)}`;}
const range=(a,b,suffix='')=>a==null?'—':(a===b?num(a):num(a)+'~'+num(b))+suffix;
const shortAddress=a=>a.replace(/^경기도\s+/,'').replace(/\([^)]*\)/g,' ').replace(/\s+/g,' ').trim();
const name=b=>b.group.replace(/^[가-힣]+시?\(/,'').replace(/\)$/,'');
const app=$('.app-shell');
let saved;try{saved=new Set(JSON.parse(localStorage.getItem('jeonse-saved-v2')||'[]'));}catch{saved=new Set();}
let state={query:'',city:'',deposit:'',area:'',rooms:'',type:'',elevator:false,savedOnly:false,sort:'name',ascending:true,selected:null,inMap:false,labels:false};
let filtered=[],map,clusters,markers=new Map(),detailSort={key:'deposit',asc:true},tableState={key:'id',asc:true,search:'',buildingId:null},viewerZoom=100,toastTimer;
const originalById=new Map(D.buildings.map(b=>[b.id,b]));
const everyUnit=D.buildings.flatMap(b=>b.units.map(u=>({...u,buildingId:b.id,city:b.city})));
const xlsx=D.meta.commonFiles.find(f=>f.type==='xlsx');
$('#notice-date').textContent=D.meta.noticeDate.replaceAll('-','.');
$('#source-summary').textContent=`원본 ${D.meta.totalUnits}세대 · ${D.meta.totalBuildings}주소`;
$('#documents-title').textContent=D.meta.title;
$('#source-link').href=D.meta.sourceUrl;
const cities=[...new Set(D.buildings.map(b=>b.city))].sort((a,b)=>a.localeCompare(b,'ko'));
$('#city').innerHTML+=[...cities].map(c=>`<option>${esc(c)}</option>`).join('');
$('#rooms-filter').innerHTML+=[...new Set(everyUnit.map(u=>u.rooms).filter(v=>v!=null))].sort((a,b)=>a-b).map(v=>`<option value="${v}">방 ${v}개</option>`).join('');
$('#type-filter').innerHTML+=[...new Set(everyUnit.map(u=>u.type))].sort().map(v=>`<option>${esc(v)}</option>`).join('');
function notify(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,3000);}
function unitPass(u,b){
 if(state.deposit&&!(u.deposit!=null&&u.deposit<=+state.deposit))return false;
 if(state.area){const [lo,hi]=state.area.split('-').map(Number);if(!(u.area!=null&&u.area>=lo&&u.area<hi))return false;}
 if(state.rooms&&u.rooms!==+state.rooms)return false;
 if(state.type&&u.type!==state.type)return false;
 if(state.elevator&&!u.elevator)return false;
 if(state.query){const q=state.query.toLocaleLowerCase();const text=[b.group,b.address,u.building,u.unit,u.notes,u.type,`${u.building}동 ${u.unit}호`].join(' ').toLocaleLowerCase();if(!text.includes(q))return false;}
 return true;
}
function aggregate(b,units){const deposits=units.map(u=>u.deposit).filter(v=>v!=null),areas=units.map(u=>u.area).filter(v=>v!=null);return {...b,visibleUnits:units,visibleCount:units.length,minDeposit:deposits.length?Math.min(...deposits):null,maxDeposit:deposits.length?Math.max(...deposits):null,minArea:areas.length?Math.min(...areas):null,maxArea:areas.length?Math.max(...areas):null,rooms:[...new Set(units.map(u=>u.rooms).filter(v=>v!=null))].sort((a,b)=>a-b),types:[...new Set(units.map(u=>u.type))]};}
function getFiltered(ignoreBounds=false){return D.buildings.filter(b=>(!state.city||b.city===state.city)&&(!state.savedOnly||saved.has(b.id))&&(!state.inMap||ignoreBounds||map.getBounds().contains([b.lat,b.lng]))).map(b=>aggregate(b,b.units.filter(u=>unitPass(u,b)))).filter(b=>b.visibleCount).sort((a,b)=>{
 const k=state.sort;let va,vb;
 if(k==='name'){va=a.group;vb=b.group;}else if(k==='address'){va=a.address;vb=b.address;}else if(k==='deposit'){va=a.minDeposit;vb=b.minDeposit;}else if(k==='area'){va=a.minArea;vb=b.minArea;}else if(k==='rooms'){va=a.rooms[0];vb=b.rooms[0];}else if(k==='units'){va=a.visibleCount;vb=b.visibleCount;}else if(k==='media'){va=a.media.length;vb=b.media.length;}else if(k==='elevator'){va=Number(a.elevator);vb=Number(b.elevator);}else{va=a.types.join();vb=b.types.join();}
 if(va==null&&vb!=null)return 1;if(vb==null&&va!=null)return -1;
 const c=typeof va==='number'?va-vb:String(va??'').localeCompare(String(vb??''),'ko',{numeric:true});return (c||a.address.localeCompare(b.address,'ko'))*(state.ascending?1:-1);
 });}
function update(){
 filtered=getFiltered();const total=filtered.reduce((sum,b)=>sum+b.visibleCount,0);
 $('#results-title').textContent=state.savedOnly?'저장한 주택':'전체 주택';
 $('#results-count').textContent=`${filtered.length}곳 · ${num(total)}세대`;
 $('#clear-search').hidden=!state.query;
 $('#sort-direction').textContent=state.ascending?'↑':'↓';$('#sort-direction').title=state.ascending?'오름차순':'내림차순';
 $$('select').forEach(s=>s.classList.toggle('active',!!s.value&&s.id!=='sort'));
 $('#elevator-filter').classList.toggle('active',state.elevator);$('#elevator-filter').setAttribute('aria-pressed',String(state.elevator));
 $('#saved-count').hidden=!saved.size;$('#saved-count').textContent=saved.size;
 $$('.rail-button').forEach(b=>b.classList.toggle('active',b.dataset.action===(state.savedOnly?'saved-view':'map-view')));
 $('#result-list').innerHTML=filtered.length?filtered.map(b=>card(b)).join(''):`<div class="empty-state">${svg(state.savedOnly?'bookmark':'search')}<strong>${state.savedOnly?'저장한 주택이 없습니다':'검색 결과가 없습니다'}</strong>${state.savedOnly?'건물 카드의 저장 버튼을 눌러 모아보세요.':'검색어와 필터를 변경해 보세요.'}</div>`;
 updateMarkers();
 $('#map-status').textContent=`${num(filtered.length)}개 주소 표시 · ${num(total)}세대`;
 if(state.selected){const selected=filtered.find(b=>b.id===state.selected);if(selected)renderDetail(selected);else closeDetail();}
 if(!$('#table-panel').hidden)renderTable();
}
function card(b){return `<article class="property-card ${b.id===state.selected?'selected':''}" data-building="${b.id}" tabindex="0" role="button" aria-label="${esc(b.group)} ${esc(b.address)} 상세보기"><div class="card-top"><span class="city-tag">${esc(b.city)} · ${esc(b.types.join(' / '))}</span><button class="card-save ${saved.has(b.id)?'saved':''}" data-save="${b.id}" aria-label="${esc(b.group)} ${saved.has(b.id)?'저장 해제':'저장'}" aria-pressed="${saved.has(b.id)}">${svg('bookmark',saved.has(b.id))}</button></div><div class="card-main"><div class="card-text"><h3>${esc(b.group)}</h3><p class="card-address">${esc(shortAddress(b.address))}</p><div class="card-price"><small>보증금</small>${esc(money(b.minDeposit))}${b.minDeposit!==b.maxDeposit?'<small>부터</small>':''}</div></div>${b.thumbnail?`<img class="card-thumb" src="${b.thumbnail}" alt="${esc(b.group)} 홍보물 첫 페이지" loading="lazy">`:`<div class="card-placeholder">${svg('house')}</div>`}</div><div class="card-meta"><span>${range(b.minArea,b.maxArea,'㎡')}</span><span>방 ${b.rooms.map(num).join('·')}개</span><span>${b.elevator?'승강기 있음':'승강기 없음'}</span><span>${b.visibleCount}세대</span></div><div class="card-media"><span>${svg('image')}${b.media.length?`홍보물 ${b.media.length}개`:'홍보물 미등록'}</span><span>상세 보기 →</span></div></article>`;}
function markerIcon(b){return L.divIcon({className:'price-marker',html:`<div class="price-pin ${b.id===state.selected?'selected':''}">${esc(money(b.minDeposit))}</div>`,iconSize:[78,32],iconAnchor:[39,38]});}
function setupMap(){
 map=L.map('map',{zoomControl:false,maxZoom:19,minZoom:7}).setView([37.28,127.03],10);
 let tileErrors=0;
 const tileUrl='https://tile.openstreetmap.org/{z}/{x}/{y}.png';
 const tiles=L.tileLayer(tileUrl,{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'}).addTo(map);
 tiles.on('tileerror',()=>{if(++tileErrors>4)$('#tile-error').hidden=false;});tiles.on('tileload',()=>{$('#tile-error').hidden=true;tileErrors=0;});
 L.control.scale({imperial:false,position:'bottomleft'}).addTo(map);
 clusters=L.markerClusterGroup({maxClusterRadius:38,showCoverageOnHover:false,zoomToBoundsOnClick:false,spiderfyOnMaxZoom:true,spiderfyDistanceMultiplier:1.8,iconCreateFunction:c=>L.divIcon({html:`<span>${c.getChildCount()}</span>`,className:'cluster-marker',iconSize:[44,44]})});
 clusters.on('clusterclick',e=>{const children=e.layer.getAllChildMarkers(),bounds=e.layer.getBounds();if(bounds.getNorth()-bounds.getSouth()<.00002&&bounds.getEast()-bounds.getWest()<.00002){const content=`<div class="cluster-options"><strong>같은 위치의 건물·주소 ${children.length}곳</strong>${children.map(m=>`<button data-pick="${m.options.buildingId}" style="display:block;text-align:left;padding:10px 0;border-bottom:1px solid #edf0ee;max-width:280px;font-size:11px;line-height:1.7">${esc(originalById.get(m.options.buildingId).address)}</button>`).join('')}</div>`;L.popup({maxWidth:310}).setLatLng(e.latlng).setContent(content).openOn(map);}else map.fitBounds(bounds,{padding:[55,80],maxZoom:17});});
 map.addLayer(clusters);
 map.on('moveend',()=>{if(state.inMap)update();});
}
function updateMarkers(){
 clusters.clearLayers();markers.clear();
 for(const b of filtered){const m=L.marker([b.lat,b.lng],{icon:markerIcon(b),buildingId:b.id,title:b.group+' · '+b.address,keyboard:true});m.bindTooltip(`<strong>${esc(b.group)}</strong><br>${esc(b.address)}<br>보증금 ${priceRange(b.minDeposit,b.maxDeposit)} · ${b.visibleCount}세대`,{direction:'top',offset:[0,-32],className:'map-tooltip',permanent:state.labels});m.on('click',()=>selectBuilding(b.id));markers.set(b.id,m);clusters.addLayer(m);}
}
function fitAll(){const list=getFiltered(true);if(!list.length){notify('표시할 주택이 없습니다.');return;}map.fitBounds(L.latLngBounds(list.map(b=>[b.lat,b.lng])),{paddingTopLeft:[55,120],paddingBottomRight:[70,90],maxZoom:15});}
function selectBuilding(id){
 const b=filtered.find(b=>b.id===id)||originalById.get(id);if(!b)return;
 state.selected=id;map.closePopup();app.classList.remove('show-list');app.classList.add('detail-open');$('#mobile-list').textContent='목록 보기';
 $('#detail').hidden=false;renderDetail(b.visibleUnits?b:aggregate(b,b.units));
 $$('.property-card').forEach(c=>c.classList.toggle('selected',c.dataset.building===id));
 for(const [mid,m] of markers){const mb=filtered.find(x=>x.id===mid);if(mb)m.setIcon(markerIcon(mb));}
 const width=window.innerWidth;const offset=width>1200?-210:0;
 const point=map.project([b.lat,b.lng],Math.max(map.getZoom(),15));map.setView(map.unproject(point.subtract([offset,0]),Math.max(map.getZoom(),15)),Math.max(map.getZoom(),15),{animate:true});
}
function closeDetail(){state.selected=null;$('#detail').hidden=true;app.classList.remove('detail-open');$$('.property-card.selected').forEach(c=>c.classList.remove('selected'));for(const [id,m] of markers){const b=filtered.find(x=>x.id===id);if(b)m.setIcon(markerIcon(b));}}
function toggleSave(id){saved.has(id)?saved.delete(id):saved.add(id);try{localStorage.setItem('jeonse-saved-v2',JSON.stringify([...saved]));}catch{}update();}
function mediaCard(m){const badge=m.match==='group'?'주택군 공통':m.match==='location'?'같은 위치 자료':m.match==='address'?'주소 일치':m.type.toUpperCase();return `<button class="media-card" data-media="${m.id}" title="${esc(m.name)} 미리보기">${m.thumbnail?`<img src="${m.thumbnail}" alt="${esc(m.name)} 썸네일" loading="lazy">`:`<span class="file-download-icon">${m.type.toUpperCase()}</span>`}<div><span class="match-tag ${m.match==='group'?'group':''}">${badge}</span><h4>${esc(m.name)}</h4><p>${m.pageCount?`${m.pageCount}페이지 · 이미지로 보기`:'원본 다운로드'}${m.match==='group'?'<br>같은 주택군에 등록된 자료':''}</p></div></button>`;}
function renderDetail(b){
 const units=[...(b.visibleUnits||b.units)].sort((a,b)=>(a.deposit??Infinity)-(b.deposit??Infinity));
 const media=b.media;const hasMissing=units.some(u=>u.area==null);
 $('#detail').innerHTML=`<div class="detail-top"><span>주택목록 · 건물 상세</span><div><button class="card-save ${saved.has(b.id)?'saved':''}" data-save="${b.id}" aria-label="선택한 건물 ${saved.has(b.id)?'저장 해제':'저장'}">${svg('bookmark',saved.has(b.id))}</button><button class="icon-button" data-action="close-detail" aria-label="상세정보 닫기">×</button></div></div><div class="detail-content"><div class="detail-city">${esc(b.city)} · ${esc(b.types.join(' / '))}</div><h2>${esc(b.group)}</h2><p class="detail-address">${esc(b.address)}</p><div class="address-actions"><button data-copy-address="${b.id}">주소 복사</button><a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(b.address)}" target="_blank" rel="noopener">Google 지도 ↗</a><a href="https://map.naver.com/p/search/${encodeURIComponent(b.address)}" target="_blank" rel="noopener">네이버 지도 ↗</a></div><div class="detail-price"><span>임대보증금</span><strong>${priceRange(b.minDeposit,b.maxDeposit)}</strong><small>주택목록 원본 기준 · ${units.length}세대${units.length!==b.units.length?' (현재 필터 적용)':''}</small></div><dl class="stats-grid"><div><dt>실사용면적</dt><dd>${range(b.minArea,b.maxArea,'㎡')}</dd></div><div><dt>방수</dt><dd>${b.rooms.map(num).join(' · ')}개</dd></div><div><dt>승강기</dt><dd>${b.elevator?'있음':'없음'}</dd></div><div><dt>공급형</dt><dd>${esc([...new Set(units.map(u=>u.areaBand))].join(' / '))}</dd></div></dl><section class="detail-section"><div class="section-title"><h3>세대별 임대조건 <span>${units.length}</span></h3><button class="text-button" data-unit-table="${b.id}">전체 항목 비교 ↗</button></div>${hasMissing?'<p class="media-caption">일부 세대의 실사용면적은 원본 엑셀에서 비어 있습니다.</p>':''}<div class="unit-mini"><table><thead><tr><th>동·호</th><th>면적(㎡)</th><th>보증금</th></tr></thead><tbody>${units.slice(0,5).map(u=>`<tr><td>${esc(u.building?u.building+'동 ':'')}${esc(u.unit)}호</td><td>${num(u.area)}</td><td>${money(u.deposit)}</td></tr>`).join('')}</tbody></table><button data-unit-table="${b.id}">${units.length>5?`${units.length}세대 모두 보기`:'동호수·층·면적 등 전체 항목 보기'} →</button></div></section><section class="detail-section"><div class="section-title"><h3>홍보물·평면도 <span>${media.length}</span></h3><span class="eyebrow">웹 미리보기</span></div>${media.some(m=>m.match==='group')?'<p class="media-caption">‘주택군 공통’ 자료는 선택한 건물과 다른 동·주소를 포함할 수 있습니다.</p>':''}${media.length?media.map(mediaCard).join(''):'<div class="empty-state" style="padding:25px 0"><strong>LH 등록 홍보물이 없습니다</strong>세대 정보는 주택목록 엑셀에서 확인할 수 있습니다.</div>'}</section><p class="coordinate-note">원본 주소를 보존해 표시했습니다. 도로명 주소가 같은 동은 지도에서 같은 위치에 묶입니다.<br><a href="${esc(b.coordinateSource)}" target="_blank" rel="noopener">주소 위치 확인 출처 ↗</a></p></div>`;
}
const columns=[['id','순번','number'],['province','시도'],['supplyRegion','시군구'],['group','모집단위(주택군)','building'],['address','주소'],['building','동'],['unit','호'],['areaBand','공급형'],['area','실사용면적(㎡)','number'],['expandedArea','확장면적(㎡)','number'],['exclusiveArea','전용면적(㎡)','number'],['rooms','방수','number'],['floor','층수'],['elevator','승강기'],['type','주택유형'],['deposit','임대보증금(원)','number'],['notes','비고']];
function tableUnits(){const allowed=new Map(filtered.map(b=>[b.id,new Set(b.visibleUnits.map(u=>u.id))]));return everyUnit.filter(u=>allowed.get(u.buildingId)?.has(u.id)&&(!tableState.buildingId||u.buildingId===tableState.buildingId)&&(!tableState.search||columns.map(([k])=>u[k]).join(' ').toLowerCase().includes(tableState.search.toLowerCase()))).sort((a,b)=>{
 const k=tableState.key,va=a[k],vb=b[k];if(va==null&&vb!=null)return 1;if(vb==null&&va!=null)return -1;let c;if(typeof va==='number')c=va-vb;else if(typeof va==='boolean')c=+va-+vb;else c=String(va??'').localeCompare(String(vb??''),'ko',{numeric:true});return (c||a.id-b.id)*(tableState.asc?1:-1);
 });}
function renderTable(){const units=tableUnits();$('#table-count').textContent=`${num(units.length)}세대`;$('#unit-table thead').innerHTML=`<tr>${columns.map(([key,label])=>`<th class="${tableState.key===key?'sorted':''}" aria-sort="${tableState.key===key?(tableState.asc?'ascending':'descending'):'none'}"><button data-column="${key}">${label}<span>${tableState.key===key?(tableState.asc?'↑':'↓'):'↕'}</span></button></th>`).join('')}</tr>`;
 $('#unit-table tbody').innerHTML=units.length?units.map(u=>`<tr>${columns.map(([key,label,type])=>`<td class="${type==='number'?'num':''}">${type==='building'?`<button data-table-building="${u.buildingId}">${esc(u[key])} ↗</button>`:key==='elevator'?(u.elevator?'있음':'없음'):type==='number'?num(u[key]):esc(u[key]||'—')}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${columns.length}" style="text-align:center;padding:50px;color:#8b9b91">조건에 맞는 세대가 없습니다.</td></tr>`;
}
function openTable(id=null){tableState.buildingId=id;tableState.search='';$('#table-search').value='';$('#table-panel').hidden=false;renderTable();$$('.rail-button').forEach(b=>b.classList.toggle('active',b.dataset.action==='table-view'));}
function closeTable(){$('#table-panel').hidden=true;$$('.rail-button').forEach(b=>b.classList.toggle('active',b.dataset.action===(state.savedOnly?'saved-view':'map-view')));}
function exportCSV(){const rows=[columns.map(c=>c[1]),...tableUnits().map(u=>columns.map(([k])=>k==='elevator'?(u[k]?'Y':'N'):(u[k]??'')))];const text='\ufeff'+rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');download(new Blob([text],{type:'text/csv;charset=utf-8'}),'든든전세_세대비교.csv');}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
function openMedia(id){const file=D.attachments[id];if(!file)return;if(!file.pages.length){const a=document.createElement('a');a.href=file.url;a.download=file.name;a.click();return;}
 viewerZoom=100;$('#viewer-zoom').textContent='100%';$('#viewer-kind').textContent=`${file.type.toUpperCase()} · ${file.pageCount}페이지`;
 $('#viewer-title').textContent=file.name;$('#viewer-download').href=file.url;$('#viewer-download').download=file.name;$('#viewer-pages').textContent=`전체 ${file.pageCount}페이지`;
 $('#viewer-body').innerHTML=file.pages.map((url,i)=>`<figure class="preview-page"><img src="${url}" alt="${esc(file.name)} ${i+1}페이지" ${i?'loading="lazy"':''}><figcaption>${i+1} / ${file.pageCount}</figcaption></figure>`).join('');
 $('#viewer').showModal();$('#viewer-body').scrollTop=0;
}
function zoomPreview(delta){viewerZoom=Math.max(50,Math.min(200,viewerZoom+delta));$('#viewer-zoom').textContent=viewerZoom+'%';$$('.preview-page').forEach(p=>p.style.width=`${Math.min(900,Math.max(200,$('#viewer-body').clientWidth-48))*viewerZoom/100}px`);}
function openDocuments(){$('#common-files').innerHTML=D.meta.commonFiles.map(mediaCard).join('');$('#documents').showModal();}
async function copyAddress(id){const b=originalById.get(id);try{await navigator.clipboard.writeText(b.address);notify('주소를 복사했습니다.');}catch{notify('복사가 제한되었습니다. 상세정보의 주소를 선택해 복사하세요.');}}
function reset(){state={...state,query:'',city:'',deposit:'',area:'',rooms:'',type:'',elevator:false,savedOnly:false,inMap:false};$('#search').value='';for(const id of ['city','deposit-filter','area-filter','rooms-filter','type-filter'])$('#'+id).value='';$('#in-map').checked=false;update();fitAll();}
document.addEventListener('click',event=>{
 const t=event.target.closest('button,a,[data-building]');if(!t)return;
 if(t.dataset.save){event.stopPropagation();toggleSave(t.dataset.save);return;}
 if(t.dataset.media){openMedia(t.dataset.media);return;}
 if(t.dataset.pick){selectBuilding(t.dataset.pick);return;}
 if(t.dataset.unitTable){openTable(t.dataset.unitTable);return;}
 if(t.dataset.tableBuilding){closeTable();selectBuilding(t.dataset.tableBuilding);return;}
 if(t.dataset.copyAddress){copyAddress(t.dataset.copyAddress);return;}
 if(t.dataset.column){tableState.asc=tableState.key===t.dataset.column?!tableState.asc:true;tableState.key=t.dataset.column;renderTable();return;}
 if(t.dataset.building){selectBuilding(t.dataset.building);return;}
 const action=t.dataset.action;
 if(action==='map-view'){closeTable();state.savedOnly=false;update();if(window.innerWidth<=800)app.classList.toggle('show-list');}
 if(action==='saved-view'){closeTable();state.savedOnly=!state.savedOnly;update();app.classList.add('show-list');}
 if(action==='table-view')openTable();
 if(action==='close-table')closeTable();
 if(action==='close-detail')closeDetail();
 if(action==='documents')openDocuments();
 if(action==='source-xlsx'&&xlsx)openMedia(xlsx.id);
});
$('#search').addEventListener('input',e=>{state.query=e.target.value.trim();update();});
$('#clear-search').onclick=()=>{$('#search').value='';state.query='';update();};
for(const [id,key] of [['city','city'],['deposit-filter','deposit'],['area-filter','area'],['rooms-filter','rooms'],['type-filter','type'],['sort','sort']])$('#'+id).addEventListener('change',e=>{state[key]=e.target.value;update();if(id==='city')fitAll();});
$('#elevator-filter').onclick=()=>{state.elevator=!state.elevator;update();};
$('#sort-direction').onclick=()=>{state.ascending=!state.ascending;update();};
$('#reset-filters').onclick=reset;
$('#fit-all').onclick=fitAll;$('#zoom-in').onclick=()=>map.zoomIn();$('#zoom-out').onclick=()=>map.zoomOut();
$('#toggle-labels').onclick=()=>{state.labels=!state.labels;$('#toggle-labels').setAttribute('aria-pressed',String(state.labels));updateMarkers();};
$('#in-map').onchange=e=>{state.inMap=e.target.checked;update();};
$('#mobile-list').onclick=()=>{app.classList.toggle('show-list');$('#mobile-list').textContent=app.classList.contains('show-list')?'지도 보기':'목록 보기';};
$('#table-search').oninput=e=>{tableState.search=e.target.value.trim();renderTable();};
$('#csv-export').onclick=exportCSV;
$('#viewer-close').onclick=()=>$('#viewer').close();$('#documents-close').onclick=()=>$('#documents').close();
$('#viewer-zoom-in').onclick=()=>zoomPreview(25);$('#viewer-zoom-out').onclick=()=>zoomPreview(-25);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if($('#viewer').open||$('#documents').open)return;if(!$('#table-panel').hidden)closeTable();else closeDetail();}if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-building]')){e.preventDefault();selectBuilding(e.target.dataset.building);}});
for(const dialog of [$('#viewer'),$('#documents')])dialog.addEventListener('click',e=>{if(e.target===dialog){const rect=dialog.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)dialog.close();}});
setupMap();update();fitAll();
})();
