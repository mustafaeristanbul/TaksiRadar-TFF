#!/usr/bin/env python3
"""TaksiRadar TFF kaynak testi v2. Yalnizca resmi fikstur tablosunu okur."""
import argparse, csv, json, re, sys, urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
URL='https://www.tff.org/?pageID=198'
HOME=('GALATASARAY','BEŞİKTAŞ','FENERBAHÇE','KASIMPAŞA','EYÜPSPOR','İSTANBUL BAŞAKŞEHİR','FATİH KARAGÜMRÜK')
class FixtureParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.cell=None;self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if tag=='tr' and 'haftaninMaclariTr' in a.get('class','').split():self.row={};self.cell=None
        elif tag=='td' and self.row is not None:
            self.cell=a.get('class','').split()[0] if a.get('class') else None
            if self.cell:self.row.setdefault(self.cell,'')
        elif tag=='a' and self.row is not None and self.cell=='haftaninMaclariDetay':
            href=a.get('href','')
            if re.search(r'macId=\d+',href,re.I):self.row['detail_url']=urljoin(URL,href)
    def handle_data(self,data):
        if self.row is not None and self.cell and not self.skip:self.row[self.cell]+=data+' '
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag=='td':self.cell=None
        elif tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None;self.cell=None

def parse(raw):
    p=FixtureParser();p.feed(raw)
    out=[];seen=set()
    for row in p.rows:
        dt=' '.join(row.get('haftaninMaclariTarih','').split())
        m=re.fullmatch(r'(\d{2}\.\d{2}\.20\d{2})\s+(\d{2}:\d{2})',dt)
        home=' '.join(row.get('haftaninMaclariEv','').split())
        away=' '.join(row.get('haftaninMaclariDeplasman','').split())
        if not m or not home or not away:continue
        if not any(home.upper().startswith(t) for t in HOME):continue
        try:datetime.strptime(dt,'%d.%m.%Y %H:%M')
        except ValueError:continue
        detail=row.get('detail_url','')
        if not re.search(r'macId=\d+',detail,re.I):continue
        key=(m.group(1),m.group(2),home,away)
        if key in seen:continue
        seen.add(key)
        out.append({'tarih':m.group(1),'baslangic':m.group(2),'ev_sahibi':home,'deplasman':away,
                    'stadyum':'DOĞRULANMADI','bitis':'BİLİNMİYOR','mac_detay':detail,'kaynak':URL,
                    'durum':'ADAY - stadyum doğrulaması gerekli'})
    return out,len(p.rows)

def main():
    a=argparse.ArgumentParser();a.add_argument('--html');a.add_argument('--test',action='store_true');a.add_argument('--out',default='tff_istanbul_adaylari.csv');args=a.parse_args()
    if args.test:
        sample='''<tr class="haftaninMaclariTr"><td class="haftaninMaclariTarih"><span>09.10.2026</span><span>20:00</span></td><td class="haftaninMaclariEv">GALATASARAY A.Ş.</td><td class="haftaninMaclariSkor">-</td><td class="haftaninMaclariDeplasman">KASIMPAŞA A.Ş.</td><td class="haftaninMaclariDetay"><a href="Default.aspx?pageId=29&amp;macId=317844">Detaylar</a></td></tr>'''
        result,n=parse(sample);assert n==1 and len(result)==1 and result[0]['ev_sahibi']=='GALATASARAY A.Ş.'
        print('YAPISAL ÖRNEK TEST BAŞARILI');return
    try:
        if args.html:
            data=Path(args.html).read_bytes()
        else:
            req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=20) as r:
                if r.status!=200:raise ValueError(f'HTTP {r.status}')
                data=r.read(2_000_001)
                if len(data)>2_000_000:raise ValueError('Sayfa 2MB sinirini asti')
        raw=data.decode('cp1254',errors='replace')
        result,total=parse(raw)
    except Exception as e:
        print('KAYNAK HATASI:',e,file=sys.stderr);sys.exit(2)
    print(f'TFF tablo satiri: {total}; Istanbul ev sahibi aday: {len(result)}')
    if not result:
        print('0 KAYIT: veri aktarimi yapilmadi.',file=sys.stderr);sys.exit(3)
    with open(args.out,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=result[0].keys(),delimiter=';');w.writeheader();w.writerows(result)
    print(json.dumps(result,ensure_ascii=False,indent=2));print('CSV:',args.out)
if __name__=='__main__':main()
