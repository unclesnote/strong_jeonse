#!/usr/bin/env python3
"""Read the corrected LH XLSX directly, retaining every source cell."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as E,re,os
root=Path(__file__).resolve().parents[2]
pan=os.environ.get('LH_PAN_ID','2015122300020927'); output=root/'outputs'/('lh_'+pan)
manifest=json.loads((output/'manifest.json').read_text());p=next((output/'공고첨부').glob('*.xlsx'))
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(p) as z:
 ss=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
 sheet=E.fromstring(z.read('xl/worksheets/sheet1.xml')); rows=[];intro=[];columns={}
 for row in sheet.findall('m:sheetData/m:row',ns):
  vals={}
  for c in row:
   v=c.find('m:v',ns);inline=c.find('m:is',ns)
   vals[re.sub(r'\d','',c.attrib['r'])]=ss[int(v.text)] if c.get('t')=='s' else (''.join(inline.itertext()) if inline is not None else (v.text if v is not None else ''))
  rowno=int(row.attrib['r'])
  if rowno<5 and vals.get('A'):intro.append(vals['A'])
  if rowno==6:columns={k:v.replace('\n',' ') for k,v in vals.items()};columns['A']='순번'
  if rowno>=7 and vals.get('E') and vals.get('A','').isdigit():
   def num(k):
    try:return float(vals.get(k,''))
    except:return None
   rows.append(dict(id=int(vals['A']),province=vals.get('B',''),supplyRegion=vals.get('C',''),group=vals['D'],address=vals['E'],building=vals.get('F',''),unit=vals.get('G',''),areaBand=vals.get('H',''),area=num('I'),expandedArea=num('J'),exclusiveArea=num('K'),rooms=num('L'),floor=vals.get('M',''),elevator=vals.get('N')=='Y',type=vals.get('O',''),deposit=num('P'),notes=vals.get('Q',''),sourceRow=rowno,rawFields=vals))
notice=re.search(r'\d{4}\.\d{2}\.\d{2}',intro[0]).group().replace('.','-')
data={'title':manifest['title'],'sourceUrl':manifest['url'],'noticeDate':notice,'collectedDate':'2026-10-21','spreadsheet':{'id':next(r['id'] for r in manifest['records'] if r.get('path','').endswith('.xlsx')),'name':p.name,'columns':columns,'notices':intro},'units':rows,'brochures':[r for r in manifest['records'] if r.get('path') and r['kind']=='홍보물'],'commonFiles':[r['id'] for r in manifest['records'] if r.get('path') and r['kind']=='공고 첨부'],'housing':manifest['housingRows']}
Path(__file__).with_name('source-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(json.dumps({'noticeDate':notice,'units':len(rows),'addresses':len(set(r['address'] for r in rows)),'groups':len(set(r['group'] for r in rows)),'brochureFiles':len(data['brochures']),'commonFiles':data['commonFiles'],'columns':columns},ensure_ascii=False,indent=2))
