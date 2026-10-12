#!/usr/bin/env python3
"""TaksiRadar V6.10 - guvenli fikstur fark kontrolu (sadece simulasyon).
Gercek bildirim gondermez, V6.8 durum dosyasini degistirmez.
"""
import argparse
import json
from pathlib import Path

def read_events(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Etkinlik JSON'u dizi olmali")
    ids = [str(x.get("mac_id", "")) for x in data if isinstance(x, dict)]
    if len(ids) != len(data) or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Eksik veya tekrar eden mac_id")
    return {str(x["mac_id"]): x for x in data}

def analyze(old, new, source_ok, confirmed_cancel_ids=()):
    if not source_ok:
        return [{"mac_id": mid, "karar": "BEKLET_KAYNAK_HATASI"} for mid in sorted(old)]
    confirmed = set(confirmed_cancel_ids)
    out = []
    for mid in sorted(old):
        if mid not in new:
            decision = "IPTAL_DOGRULANDI" if mid in confirmed else "BEKLET_DETAY_DOGRULAMASI"
        elif old[mid] != new[mid]:
            decision = "DEGISIKLIK_YENIDEN_DOGRULA"
        else:
            decision = "DEGISIKLIK_YOK"
        out.append({"mac_id": mid, "karar": decision})
    for mid in sorted(set(new) - set(old)):
        out.append({"mac_id": mid, "karar": "YENI_MAC_DOGRULA"})
    return out

def selftest():
    old = {"1": {"mac_id": "1"}, "2": {"mac_id": "2"}}
    new = {"2": {"mac_id": "2"}}
    assert analyze(old, new, True)[0]["karar"] == "BEKLET_DETAY_DOGRULAMASI"
    assert analyze(old, new, True, ["1"])[0]["karar"] == "IPTAL_DOGRULANDI"
    assert all(x["karar"] == "BEKLET_KAYNAK_HATASI" for x in analyze(old, new, False))
    assert analyze(old, old, True)[0]["karar"] == "DEGISIKLIK_YOK"
    print("V6.10 TEST BASARILI: kaybolan mac, dogrulanmis iptal, kaynak hatasi, degisiklik yok")
    print("BILDIRIM GONDERILMEDI; DURUM DOSYASI DEGISTIRILMEDI")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--eski")
    ap.add_argument("--yeni")
    ap.add_argument("--kaynak-hatasi", action="store_true")
    args = ap.parse_args()
    if args.test:
        selftest()
        return
    if not args.eski or not args.yeni:
        ap.error("--eski ve --yeni gerekli")
    old, new = read_events(args.eski), read_events(args.yeni)
    # Bu arac TFF'den bagimsiz iptal teyidi yapmaz. Sadece supheli kaydi bekletir.
    for row in analyze(old, new, not args.kaynak_hatasi):
        print(row["mac_id"], row["karar"])
    print("SADECE SIMULASYON; GERCEK TFF IPTAL DOGRULAMASI VE BILDIRIM YOK")

if __name__ == "__main__":
    main()
