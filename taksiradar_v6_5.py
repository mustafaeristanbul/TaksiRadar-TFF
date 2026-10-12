#!/usr/bin/env python3
"""TaksiRadar V6.5: TFF fixture -> verified stadium -> notification preview.

Run next to tff_kaynak_test_v2.py and tff_stadyum_test_v3.py.
No notifications sent; no Flutter files modified.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tff_kaynak_test_v2 import URL, parse
from tff_stadyum_test_v3 import check, fetch

STADIUMS = {
    "5018": (41.1033729, 28.9909648),
    "6097": (41.0392313, 28.9945594),
    "5372": (41.0241904, 28.6977799),
}


def build(rows, details, now):
    events = []
    for row, raw in zip(rows, details):
        verified = check(row, raw)
        if not verified["durum"].startswith("DOGRULANDI"):
            print("ATLANDI (TFF doğrulanamadı):", row["ev_sahibi"])
            continue
        sid = verified["stad_id"]
        if sid not in STADIUMS:
            print("ATLANDI (konum bilinmiyor):", sid)
            continue
        match_id = parse_qs(urlparse(row["mac_detay"]).query).get("macId", [""])[0]
        if not match_id.isdigit():
            continue
        start = datetime.strptime(row["tarih"] + " " + row["baslangic"], "%d.%m.%Y %H:%M")
        notification = start + timedelta(minutes=80)
        if notification <= now:
            print("ATLANDI (bildirim zamanı geçti):", match_id)
            continue
        lat, lon = STADIUMS[sid]
        fmt = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S")
        events.append({
            "mac_id": match_id,
            "ev_sahibi": row["ev_sahibi"],
            "deplasman": row["deplasman"],
            "stadyum": verified["stadyum"],
            "stad_id": sid,
            "enlem": lat,
            "boylam": lon,
            "baslangic": fmt(start),
            "tahmini_bitis_ilk": fmt(start + timedelta(minutes=110)),
            "tahmini_bitis_son": fmt(start + timedelta(minutes=120)),
            "bildirim_zamani": fmt(notification),
            "saat_turu": "TAHMINI",
            "saat_dilimi": "Europe/Istanbul",
            "kaynak": row["mac_detay"],
        })
    return events


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fikstur-html", help="Offline fixture HTML")
    p.add_argument("--detay-klasoru", help="Offline detail HTML directory, named macId.html")
    p.add_argument("--out", default="taksiradar_etkinlik_v6_5.json")
    p.add_argument("--test", action="store_true")
    a = p.parse_args()
    if a.test:
        now = datetime(2026, 10, 8)
        row = {"tarih":"09.10.2026","baslangic":"20:00","ev_sahibi":"GALATASARAY A.Ş.","deplasman":"KASIMPAŞA A.Ş.","mac_detay":"https://www.tff.org/Default.aspx?pageId=29&macId=317844"}
        # Test only time formatting and notification math; not stadium HTML parsing.
        start = datetime.strptime(row["tarih"] + " " + row["baslangic"], "%d.%m.%Y %H:%M")
        assert (start + timedelta(minutes=80)).strftime("%H:%M") == "21:20"
        assert (start + timedelta(minutes=110)).strftime("%H:%M") == "21:50"
        assert (start + timedelta(minutes=120)).strftime("%H:%M") == "22:00"
        assert now < start
        print("V6.5 SAAT HESAPLAMA TESTI BASARILI")
        return
    try:
        if a.fikstur_html:
            fixture = Path(a.fikstur_html).read_bytes().decode("cp1254", errors="replace")
        else:
            fixture = fetch(URL)
        rows, total = parse(fixture)
        if not rows:
            raise ValueError("TFF fikstüründe İstanbul ev sahibi adayı bulunamadı")
        details = []
        for row in rows:
            mid = parse_qs(urlparse(row["mac_detay"]).query).get("macId", [""])[0]
            if a.detay_klasoru:
                detail = (Path(a.detay_klasoru) / (mid + ".html")).read_bytes().decode("cp1254", errors="replace")
            else:
                detail = fetch(row["mac_detay"])
            details.append(detail)
        events = build(rows, details, datetime.now())
        if not events:
            raise ValueError("Gelecekte bildirim zamanı olan, stadyumu doğrulanmış maç yok")
        output = Path(a.out)
        output.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"TFF fikstür satırı: {total}; aday: {len(rows)}; etkinlik: {len(events)}")
        print("ÇIKTI:", output.resolve())
        for event in events:
            print(event["mac_id"], event["stadyum"], "BILDIRIM:", event["bildirim_zamani"])
        print("Bu yalnızca test JSON'udur; bildirim gönderilmedi.")
    except Exception as exc:
        print("V6.5 HATA - çıktı güncellenmedi:", exc, file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
