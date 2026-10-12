#!/usr/bin/env python3
"""TaksiRadar V6.11: TFF kaynak guvenligi; salt okunur, bildirim yok."""
import argparse
import json
from pathlib import Path

def load(path):
    data=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data,list):
        raise ValueError("JSON kokunde liste bekleniyor")
    ids=[str(x["mac_id"]) for x in data]
    if len(ids)!=len(set(ids)):
        raise ValueError("Tekrarlanan mac_id")
    return {str(x["mac_id"]):x for x in data}

def decide(old,new,source,details):
    if source!="ok":
        return [(mid,"BEKLET_KAYNAK_DOGRULANAMADI") for mid in sorted(old)]
    if details!="tam":
        return [(mid,"BEKLET_EKSIK_DETAY") for mid in sorted(old)]
    return [(mid,"BEKLET_MAC_DETAYINDAN_TEYIT_ET" if mid not in new else "KAYIT_VAR") for mid in sorted(old)]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--test",action="store_true")
    p.add_argument("--eski")
    p.add_argument("--yeni")
    p.add_argument("--kaynak",choices=["ok","hata","bos"],default="ok")
    p.add_argument("--detaylar",choices=["tam","eksik"],default="tam")
    a=p.parse_args()
    if a.test:
        old={"1":{},"2":{}}
        new={"2":{}}
        assert decide(old,new,"hata","tam")[0][1]=="BEKLET_KAYNAK_DOGRULANAMADI"
        assert decide(old,new,"bos","tam")[0][1]=="BEKLET_KAYNAK_DOGRULANAMADI"
        assert decide(old,new,"ok","eksik")[0][1]=="BEKLET_EKSIK_DETAY"
        assert decide(old,new,"ok","tam")[0][1]=="BEKLET_MAC_DETAYINDAN_TEYIT_ET"
        print("V6.11 TEST BASARILI: kaynak hatasi, bos kaynak, eksik detay, kayip mac")
        print("BILDIRIM YOK; DOSYA DEGISTIRILMEDI")
        return
    if not a.eski or not a.yeni:
        p.error("--eski ve --yeni gerekli")
    old=load(a.eski)
    new=load(a.yeni)
    for mid,status in decide(old,new,a.kaynak,a.detaylar):
        print(mid,status)
    print("SIMULASYON: Kaynak/detay durumu parametreyle belirtilir; gercek TFF baglantisi yapilmaz.")
    print("BILDIRIM YOK; DURUM DOSYASI DEGISTIRILMEDI")

if __name__=="__main__":
    main()
