#!/usr/bin/env python3
"""Write a portable XLSX attachment index using only the Python standard library."""
import argparse,json,zipfile
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape,quoteattr

def column(n):
    out=''
    while n:n,r=divmod(n-1,26);out=chr(65+r)+out
    return out

def build(root,output):
    data=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    records=data['records']
    tables=[('첨부파일', [['번호','구분','주택군','팝업 주소','파일명','상태','크기(bytes)','파일 경로','다운로드 URL','팝업 조회 URL']]+[[i,r['kind'],r.get('housing',''),r.get('address',''),r['name'],r.get('status',''),r.get('size'),r.get('path',''),r['url'],r['source']] for i,r in enumerate(records,1)]),('주택별 홍보물',[['주택군','팝업 주소','버튼 파일 수','확인 파일 수','조회 URL']]+[[p['housing'],'\n'.join(dict.fromkeys(x.get('dngHsAdr','') for x in p['items'])),p['count'],len(p['items']),p.get('endpoint',data['url'])] for p in data['popups']])]
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';rn='http://schemas.openxmlformats.org/officeDocument/2006/relationships';pn='http://schemas.openxmlformats.org/package/2006/relationships'
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1,2))+'</Types>')
        z.writestr('_rels/.rels',f'<Relationships xmlns="{pn}"><Relationship Id="rId1" Type="{rn}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="{rn}"><sheets>'+''.join(f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(tables,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',f'<Relationships xmlns="{pn}">'+''.join(f'<Relationship Id="rId{i}" Type="{rn}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1,2))+'</Relationships>')
        for idx,(_,rows) in enumerate(tables,1):
            links=[];xml=[]
            for rowno,row in enumerate(rows,1):
                cells=[]
                for colno,value in enumerate(row,1):
                    ref=f'{column(colno)}{rowno}';text='' if value is None else str(value)
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
                    if rowno>1 and ((idx==1 and colno in (8,9,10)) or (idx==2 and colno==5)) and text:
                        target=quote(text,safe='/()_-.') if idx==1 and colno==8 else text;links.append((ref,target))
                xml.append(f'<row r="{rowno}">'+''.join(cells)+'</row>')
            hyperlinks='<hyperlinks>'+''.join(f'<hyperlink ref="{ref}" r:id="rId{i}"/>' for i,(ref,_) in enumerate(links,1))+'</hyperlinks>' if links else ''
            z.writestr(f'xl/worksheets/sheet{idx}.xml',f'<worksheet xmlns="{ns}" xmlns:r="{rn}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="10" width="28" customWidth="1"/></cols><sheetData>'+''.join(xml)+f'</sheetData><autoFilter ref="A1:{column(len(rows[0]))}{len(rows)}"/>'+hyperlinks+'</worksheet>')
            z.writestr(f'xl/worksheets/_rels/sheet{idx}.xml.rels',f'<Relationships xmlns="{pn}">'+''.join(f'<Relationship Id="rId{i}" Type="{rn}/hyperlink" Target={quoteattr(target)} TargetMode="External"/>' for i,(_,target) in enumerate(links,1))+'</Relationships>')
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(build(a.root,a.output))
