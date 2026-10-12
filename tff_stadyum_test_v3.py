#!/usr/bin/env python3
"""TaksiRadar: TFF mac detaylarindan stadyum dogrulama; Flutter'a dokunmaz."""
import csv, json, re, sys, urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from tff_kaynak_test_v2 import parse, URL

class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stadium=None; self.stadium_url=None; self.date=None; self.title=''; self.capture=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); ident=a.get('id','')
        if tag=='a' and ident.endswith('_lnkStad'):
            self.capture='stadium'; self.stadium_url=urljoin(URL,a.get('href',''))
        elif tag=='span' and ident.endswith('_lblTarih'): self.capture='date'
        elif tag=='title':self.capture='title'
    def handle_data(self,data):
        if self.capture=='stadium':self.stadium=(self.stadium or '')+data
        elif self.capture=='date':self.date=(self.date or '')+data
        elif self.capture=='title':self.title+=data
    def handle_endtag(self,tag):
        if (tag=='a' and self.capture=='stadium') or (tag=='span' and self.capture=='date') or (tag=='title' and self.capture=='title'):self.capture=None

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=20) as r:
        if r.status!=200:raise ValueError(f'HTTP {r.status}')
        data=r.read(2_000_001)
        if len(data)>2_000_000:raise ValueError('2MB siniri asildi')
    return data.decode('cp1254',errors='replace')

def check(row,raw):
    p=DetailParser();p.feed(raw)
    name=' '.join((p.stadium or '').split()); dt=' '.join((p.date or '').split())
    title=' '.join(p.title.split()).upper()
    stadid=parse_qs(urlparse(p.stadium_url or '').query).get('stadId',[''])[0]
    result=dict(row)
    result.update(stadyum=name or 'DOĞRULANMADI',stad_id=stadid,stad_detay=p.stadium_url or '',bitis='BİLİNMİYOR')
    expected=datetime.strptime(row['tarih']+' '+row['baslangic'],'%d.%m.%Y %H:%M')
    m=re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})\s*-\s*(\d{2}:\d{2})',dt)
    date_ok=bool(m and datetime.strptime(m.group(1)+' '+m.group(2),'%d.%m.%Y %H:%M')==expected)
    def key(x):return re.sub(r'[^A-ZÇĞİÖŞÜ0-9]','',x.upper().replace('İ','İ'))
    teams_ok=key(row['ev_sahibi']) in key(title) and key(row['deplasman']) in key(title)
    city_ok=bool(re.search(r'\bİSTANBUL\b',name.upper()))
    valid=bool(date_ok and teams_ok and city_ok and stadid and p.stadium_url and urlparse(p.stadium_url).hostname in ('www.tff.org','tff.org'))
    result['durum']='DOGRULANDI - TFF mac detayinda Istanbul stadyumu' if valid else 'RED - stadyum/tarih/takim bilgisi dogrulanamadi'
    result['dogrulama']=f'tarih={date_ok}; takimlar={teams_ok}; istanbul={city_ok}; stad_id={bool(stadid)}'
    return result

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--fikstur-html',help='Kayitli TFF fikstur HTML dosyasi')
    ap.add_argument('--ilk-detay-html',help='Ilk macin kayitli detay HTML dosyasi')
    ap.add_argument('--out',default='tff_istanbul_stadyum_dogrulama.csv')
    a=ap.parse_args()
    raw=Path(a.fikstur_html).read_bytes().decode('cp1254','replace') if a.fikstur_html else fetch(URL)
    rows,total=parse(raw)
    print(f'Fikstur satiri: {total}; Istanbul ev sahibi aday: {len(rows)}')
    if not rows:sys.exit('ADAY YOK - cikti olusturulmadi')
    checked=[]
    for i,row in enumerate(rows):
        try:
            detail=Path(a.ilk_detay_html).read_bytes().decode('cp1254','replace') if i==0 and a.ilk_detay_html else fetch(row['mac_detay'])
            record=check(row,detail)
        except Exception as e:
            record=dict(row);record.update(stad_id='',stad_detay='',durum='RED - detay alinamadi',dogrulama=str(e))
        checked.append(record)
        print(f"{row['ev_sahibi']} - {row['deplasman']}: {record['stadyum']} | {record['durum']}")
    with open(a.out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(checked[0]),delimiter=';');w.writeheader();w.writerows(checked)
    print('CSV:',a.out)
    print('ONAYLI:',sum(x['durum'].startswith('DOGRULANDI') for x in checked),'/',len(checked))
    print(json.dumps(checked,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
