"""dashboard.py — trang theo dõi thực nghiệm / demo trực tiếp.

    python gateway/dashboard.py              # mở http://localhost:8000
    python gateway/dashboard.py --port 8080 --db gateway/wsn.db --mqtt-host localhost

Hai nguồn dữ liệu:
  - Lịch sử: đọc gateway/wsn.db (chỉ đọc) — mọi gói DATA, STATS, sự kiện của run, không gộp.
  - Trực tiếp: nghe MQTT `wsn/#` (gateway.py phát từng gói ngay khi Root nhận) rồi đẩy sang trình duyệt
    bằng Server-Sent Events (/api/stream) -> trễ < 0.5 s. Gateway chỉ commit SQLite mỗi 2 s nên không
    dùng DB cho phần trực tiếp.
Mở `/?run=<run_id>` để xem lại một run cũ.
"""
import argparse
import datetime as dt
import json
import os
import queue
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "gateway", "dashboard.html")
FEED_SKIP = ("ROOT_SUMMARY",)

clients = []                      # mỗi trình duyệt đang mở /api/stream có một Queue
clients_lock = threading.Lock()


def now_iso():
    return dt.datetime.now().isoformat(timespec="milliseconds")


def ts(s):
    return dt.datetime.fromisoformat(s)


def open_db(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def runs(db):
    rows = db.execute("SELECT run_id, started_at, ended_at, topology, power FROM runs "
                      "ORDER BY started_at DESC LIMIT 80").fetchall()
    return [dict(r) for r in rows]


def history(db, run_id):
    """Toàn bộ dữ liệu của một run. Thời gian tính bằng giây kể từ lúc run bắt đầu (giờ máy tính)."""
    run = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not run:
        return {"error": f"không có run {run_id}"}
    run = dict(run)
    t0 = ts(run["started_at"])
    rel = lambda h: round((ts(h) - t0).total_seconds(), 3)
    data = [[rel(r["host_ts"]), r["t_ms"], r["node"], r["boot"], r["seq"], r["hop"], r["parent"], r["via"],
             r["flags"], r["ldr"], r["i_ma_x10"], r["vbat_mv"]]
            for r in db.execute("SELECT * FROM data WHERE run_id=? ORDER BY rowid", (run_id,))]
    stats = [[rel(r["host_ts"]), r["t_ms"], r["node"], r["rtt_avg_ms"], r["retries"], r["qfull"],
              r["parent_lost"], r["rssi"], r["i_avg_x10"], r["gen"]]
             for r in db.execute("SELECT * FROM stats WHERE run_id=? ORDER BY rowid", (run_id,))]
    q = ",".join("?" * len(FEED_SKIP))
    events = [[rel(r["host_ts"]), r["t_ms"], r["type"], json.loads(r["json"])]
              for r in db.execute(f"SELECT host_ts, t_ms, type, json FROM events WHERE run_id=? "
                                  f"AND type NOT IN ({q}) ORDER BY rowid", (run_id, *FEED_SKIP))]
    end = run["ended_at"]
    return {"run": run, "running": end is None, "now": now_iso(),
            "elapsed_s": round(((ts(end) if end else dt.datetime.now()) - t0).total_seconds(), 1),
            "data": data, "stats": stats, "events": events}


def start_mqtt(host, port):
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("Không có paho-mqtt -> chỉ xem lịch sử, không có phần trực tiếp")
        return False

    def on_connect(c, userdata, flags, rc, props=None):
        c.subscribe("wsn/#")

    def on_message(c, userdata, msg):
        parts = msg.topic.split("/")
        kind = parts[-1] if parts[-1] in ("data", "stats", "local") else "event"
        try:
            e = json.loads(msg.payload)
        except ValueError:
            return
        line = "data: " + json.dumps({"kind": kind, "host_ts": now_iso(), "e": e}, separators=(",", ":")) + "\n\n"
        with clients_lock:
            for q in clients:
                if q.qsize() < 5000:
                    q.put(line)

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wsn-dashboard-{os.getpid()}")
    c.on_connect = on_connect
    c.on_message = on_message
    try:
        c.connect(host, port, keepalive=30)
    except Exception as ex:
        print(f"MQTT {host}:{port} không kết nối được ({ex}) -> chỉ xem lịch sử")
        return False
    c.loop_start()
    print(f"MQTT: nghe wsn/# tại {host}:{port}")
    return True


class Handler(BaseHTTPRequestHandler):
    db_path = None
    live = False

    def send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        q = queue.Queue()
        with clients_lock:
            clients.append(q)
        try:
            self.wfile.write(f"event: hello\ndata: {json.dumps({'live': self.live, 'now': now_iso()})}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    line = q.get(timeout=10)
                except queue.Empty:
                    line = ": ping\n\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            with clients_lock:
                clients.remove(q)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                with open(HTML, encoding="utf-8") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/stream":
                return self.stream()
            db = open_db(self.db_path)
            try:
                if u.path == "/api/runs":
                    return self.send(200, json.dumps(runs(db)), "application/json")
                if u.path == "/api/history":
                    run_id = parse_qs(u.query).get("run", [""])[0]
                    if not run_id:
                        r = runs(db)
                        if not r:
                            return self.send(200, json.dumps({"error": "chưa có run nào"}), "application/json")
                        run_id = r[0]["run_id"]
                    return self.send(200, json.dumps(history(db, run_id), separators=(",", ":")),
                                     "application/json")
            finally:
                db.close()
            self.send(404, "not found", "text/plain")
        except Exception as ex:  # trang vẫn sống khi DB đang bị ghi dở
            self.send(500, json.dumps({"error": str(ex)}), "application/json")

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "gateway", "wsn.db"))
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--mqtt-host", default="localhost")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    a = ap.parse_args()
    Handler.db_path = a.db
    Handler.live = start_mqtt(a.mqtt_host, a.mqtt_port)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    print(f"Dashboard: http://localhost:{a.port}  (db={a.db})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
