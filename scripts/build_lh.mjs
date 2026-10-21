import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const workspace=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const pan=process.env.LH_PAN_ID||'2015122300020927';
const root=process.env.LH_OUTPUT_ROOT||path.join(workspace,'data/notices',`lh_${pan}`);
const source=JSON.parse(await fs.readFile(process.env.LH_SOURCE_DATA||path.join(workspace,'data/intermediate',pan,'source-data.json'),'utf8'));
const d=JSON.parse(await fs.readFile(`${root}/manifest.json`,'utf8'));
const downloaded=d.records.filter(r=>r.path).length, excluded=d.records.length-downloaded;
const wb=Workbook.create();
const files=wb.worksheets.add('첨부파일');
const houses=wb.worksheets.add('주택별 홍보물');
function base(s,title,subtitle,headers,rows,widths){
 s.showGridLines=false;
 const last=String.fromCharCode(64+headers.length);
 s.getRange(`A1:${last}${rows.length+6}`).format.font={name:'Arial',size:10,color:'#182638'};
 s.getRange('A2').values=[[title]];
 s.getRange('A2').format.font={size:15,bold:true};
 s.getRange('A3').values=[[subtitle]];
 s.getRange('A4').values=[['공고 원문']];
 s.getRange('B4').values=[['LH청약플러스 공고 열기']];
 s.getRange(`A6:${last}6`).values=[headers];
 s.getRange(`A7:${last}${rows.length+6}`).values=rows;
 s.getRange(`A6:${last}6`).format={fill:'#243F60',font:{color:'#FFFFFF',bold:true},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};
 s.getRange(`A7:${last}${rows.length+6}`).format={rowHeight:48,verticalAlignment:'center',wrapText:true};
 widths.forEach((w,i)=>s.getRange(`${String.fromCharCode(65+i)}6:${String.fromCharCode(65+i)}${rows.length+6}`).format.columnWidth=w);
 for(let i=0;i<rows.length;i++) if(i%2===1)s.getRange(`A${i+7}:${last}${i+7}`).format.fill='#F1F5F9';
 s.tables.add(`A6:${last}${rows.length+6}`,true,s.name==='첨부파일'?'AttachmentInventory':'HousingMedia');
 s.freezePanes.freezeRows(6);
 s.freezePanes.freezeColumns(3);
}
const rows=d.records.map((r,i)=>[i+1,r.kind,r.housing||'공고 공통',r.address||'해당 없음',r.name,r.name.split('.').pop().toUpperCase(),r.path?r.status:`제외(${r.name.split('.').pop().toUpperCase()})`,r.size??null,r.path?'파일 열기':'다운로드 제외',r.url]);
base(files,'든든전세 공고 첨부파일 목록',`공고일 ${source.noticeDate} / 수집일 ${source.collectedDate} / 다운로드 ${downloaded}개 / HWP·HWPX 제외 ${excluded}개`,
 ['번호','구분','주택명','홍보물 팝업 주소','원본 파일명','형식','처리 결과','크기 (bytes)','저장 파일','원본 다운로드 URL'],rows,[7,13,32,65,70,9,18,16,17,65]);
files.getRange(`H7:H${rows.length+6}`).setNumberFormat('#,##0');
for(let i=0;i<d.records.length;i++){
 const r=d.records[i],n=i+7;
 if(r.path)files.getRange(`I${n}`).values=[['파일 열기']];
 files.getRange(`J${n}`).values=[[r.url]];
}
const houseRows=d.popups.map((p,i)=>[i+1,p.housing,[...new Set(p.items.map(x=>x.dngHsAdr))].join('\n')||'홍보물 미등록',p.count,p.items.length,p.items.length?'등록':'등록된 홍보물 없음',p.apt]);
base(houses,'주택별 홍보물 확인',`${d.popups.length}개 주택군 / 홍보물 등록 ${d.popups.filter(p=>p.items.length).length}개 / 미등록 ${d.popups.filter(p=>!p.items.length).length}개`,
 ['번호','주택명','홍보물에 표시된 주소','버튼 표시 파일 수','확인 파일 수','등록 상태','주택 코드'],houseRows,[7,36,96,20,18,27,20]);
houses.freezePanes.unfreeze();houses.freezePanes.freezeRows(6);houses.freezePanes.freezeColumns(2);
for(let i=0;i<houseRows.length;i++)houses.getRange(`A${i+7}:G${i+7}`).format.rowHeight=Math.max(48,houseRows[i][2].split('\n').length*26);
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'첨부파일!A6:J10',tableMaxRows:5,tableMaxCols:10,maxChars:2000})).ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(`${root}/LH_든든전세_첨부파일정리.xlsx`);
console.log('워크북 저장 완료');
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);
if(process.env.LH_RENDER==='1') for(const [s,range,out] of [['첨부파일','B6:E9','files'],['주택별 홍보물','B6:D9','houses']]){
 const preview=await wb.render({sheetName:s,range,scale:1,format:'png'});
 await fs.writeFile(`${root}/${out}_preview.png`,new Uint8Array(await preview.arrayBuffer()));
}
