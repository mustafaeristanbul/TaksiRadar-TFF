#!/usr/bin/env python3
"""TaksiRadar V6.12: live TFF source integrity gate; read-only, no notifications."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tff_kaynak_test_v2 import URL, parse
from tff_stadyum_test_v3 import fetch, check


def verify(fetcher, parser, checker):
    report = {"kaynak": URL, "durum": "BEKLET", "neden": "", "fikstur_satiri": 0,
              "aday": 0, "dogrulanan": 0, "maclar": []}
    try:
        html = fetcher(URL)
    except Exception as exc:
        report["neden"] = "FIKSTUR_BAGLANTI_HATASI"
        report["hata_turu"] = type(exc).__name__
        return report
    try:
        rows, total = parser(html)
        report["fikstur_satiri"] = total
        report["aday"] = len(rows)
        if not rows:
            report["neden"] = "BOS_VEYA_ADAY_YOK"
            return report
        ids = []
        for row in rows:
            link = row["mac_detay"]
            parsed = urlparse(link)
            if parsed.scheme != "https" or parsed.hostname not in ("www.tff.org", "tff.org"):
                raise ValueError("TFF disi mac detayi")
            mid = parse_qs(parsed.query).get("macId", [""])[0]
            if not mid.isdigit() or mid in ids:
                raise ValueError("Gecersiz veya tekrar macId")
            ids.append(mid)
            try:
                detail = fetcher(link)
                result = checker(row, detail)
            except Exception as exc:
                report["neden"] = "EKSIK_MAC_DETAYI"
                report["hata_turu"] = type(exc).__name__
                return report
            if not result.get("durum", "").startswith("DOGRULANDI"):
                report["neden"] = "DOGRULANAMAYAN_MAC_DETAYI"
                return report
            report["maclar"].append({"mac_id": mid, "stad_id": result.get("stad_id", "")})
            report["dogrulanan"] += 1
    except Exception as exc:
        report["neden"] = "FIKSTUR_VEYA_VERI_HATASI"
        report["hata_turu"] = type(exc).__name__
        return report
    report["durum"] = "DOGRULANDI"
    report["neden"] = "TUM_ADAY_DETAYLARI_DOGRULANDI"
    return report


def test():
    row = {"mac_detay": "https://www.tff.org/Default.aspx?pageId=29&macId=1"}
    parser = lambda html: ([row], 1)
    good = lambda r, d: {"durum": "DOGRULANDI", "stad_id": "5018"}
    assert verify(lambda u: "html", parser, good)["durum"] == "DOGRULANDI"
    assert verify(lambda u: (_ for _ in ()).throw(TimeoutError()), parser, good)["neden"] == "FIKSTUR_BAGLANTI_HATASI"
    assert verify(lambda u: "html", lambda h: ([], 0), good)["neden"] == "BOS_VEYA_ADAY_YOK"
    assert verify(lambda u: "html", parser, lambda r,d: {"durum": "RED"})["neden"] == "DOGRULANAMAYAN_MAC_DETAYI"
    assert verify(lambda u: "html" if u == URL else (_ for _ in ()).throw(TimeoutError()), parser, good)["neden"] == "EKSIK_MAC_DETAYI"
    print("V6.12 TEST BASARILI: kaynak, bos liste, eksik detay, gecersiz detay, basarili dogrulama")
    print("BILDIRIM YOK; MEVCUT DOSYALAR DEGISTIRILMEDI")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--canli", action="store_true")
    ap.add_argument("--rapor", help="Yeni rapor dosyasi (istege bagli)")
    args = ap.parse_args()
    if args.test:
        test()
        return
    if not args.canli:
        ap.error("--test veya --canli belirtin")
    report = verify(fetch, parse, check)
    report["kontrol_zamani_utc"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.rapor:
        target = Path(args.rapor)
        if target.exists():
            ap.error("Rapor dosyasi zaten var; uzerine yazilmadi")
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["durum"] != "DOGRULANDI":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
