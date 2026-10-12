"""Existing V6 tools composed into an atomic, freshness-gated feed."""
import argparse
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import taksiradar_v6_5 as v65
import taksiradar_v6_10 as v610
import taksiradar_v6_11 as v611
import taksiradar_v6_12 as v612

TTL = 1200
INTERVAL = 600

def utcnow():
    return datetime.now(timezone.utc)

def fresh(data, now):
    try:
        checked = datetime.fromisoformat(data["son_basarili_kontrol_utc"])
        expiry = datetime.fromisoformat(data["gecerli_son_utc"])
        return (data["durum"] == "GUNCEL" and
                timedelta(0) <= now - checked <= timedelta(seconds=TTL) and
                checked < expiry <= checked + timedelta(seconds=TTL) and now < expiry)
    except (KeyError, TypeError, ValueError):
        return False

def refresh(previous=None, fetcher=None, parser=None, checker=None, now=None):
    previous = previous or {}
    now = now or utcnow()
    fetcher, parser, checker = fetcher or v65.fetch, parser or v65.parse, checker or v65.check
    cache = {}
    def cached(url):
        if url not in cache:
            cache[url] = fetcher(url)
        return cache[url]
    gate = v612.verify(cached, parser, checker)
    old = {str(e["mac_id"]): e for e in previous.get("maclar", [])}
    result = {"surum": 1, "saat_dilimi": "Europe/Istanbul",
              "kontrol_zamani_utc": now.isoformat(), "durum": "BEKLET",
              "son_basarili_kontrol_utc": previous.get("son_basarili_kontrol_utc"),
              "gecerli_son_utc": previous.get("gecerli_son_utc"),
              "maclar": list(old.values()), "kaynak_kontrolu": gate}
    try:
        if gate["durum"] != "DOGRULANDI":
            raise ValueError(gate["neden"])
        rows, _ = parser(cache[v65.URL])
        # V6.5 expects Istanbul wall time; never depend on host timezone.
        istanbul_now = now.astimezone(timezone(timedelta(hours=3))).replace(tzinfo=None)
        # V6.5 filters by notification time; keep ongoing matches until exit window ends.
        events = v65.build(rows, [cache[r["mac_detay"]] for r in rows],
                           istanbul_now - timedelta(hours=2))
        events = [e for e in events
                  if datetime.fromisoformat(e["tahmini_bitis_son"]) > istanbul_now]
        new = {str(e["mac_id"]): e for e in events}
        if len(new) != len(events):
            raise ValueError("TEKRAR_MAC_ID")
        result["degisiklikler"] = v610.analyze(old, new, True)
        result["guvenlik_kararlari"] = v611.decide(old, new, "ok", "tam")
        # Missing matches are held separately, never inferred cancelled.
        result["bekletilen_maclar"] = [e for mid, e in old.items() if mid not in new]
        result.update(durum="GUNCEL", maclar=events,
                      son_basarili_kontrol_utc=now.isoformat(),
                      gecerli_son_utc=(now + timedelta(seconds=TTL)).isoformat())
    except Exception as exc:
        result["neden"] = str(exc)
        result["degisiklikler"] = v610.analyze(old, {}, False)
        result["guvenlik_kararlari"] = v611.decide(old, {}, "hata", "eksik")
    return result

def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)

def public_feed(data, now=None):
    output = dict(data)
    output["guncel"] = fresh(data, now or utcnow())
    if not output["guncel"]:
        output["maclar"] = []
    # Old records remain on disk for diagnosis, never served as recommendations.
    output.pop("bekletilen_maclar", None)
    return output

def handler_for(path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/tff.json":
                self.send_error(404)
                return
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                body = json.dumps(public_feed(data), ensure_ascii=False).encode()
            except (OSError, ValueError):
                body = b'{"surum":1,"durum":"BEKLET","guncel":false,"maclar":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    return Handler

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("tff_guncel.json")))
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    def cycle():
        try:
            previous = json.loads(Path(args.out).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        result = refresh(previous)
        atomic_write(args.out, result)
        print(result["durum"], result.get("neden", ""), flush=True)
        return result
    if not args.serve:
        raise SystemExit(0 if cycle()["durum"] == "GUNCEL" else 2)
    stop = threading.Event()
    def worker():
        while not stop.is_set():
            try:
                cycle()
            except Exception as exc:
                print("YENILEME_HATASI", type(exc).__name__, flush=True)
            stop.wait(INTERVAL)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(args.out))
    print("USB feed: http://127.0.0.1:%s/tff.json" % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()

if __name__ == "__main__":
    main()
