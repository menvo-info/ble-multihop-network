"""wsn_db.py — lược đồ SQLite và hàm ghi dùng chung cho gateway.py / analyze.py.

Mỗi lần chạy thực nghiệm là một run_id. Dữ liệu tách 3 loại :
  data       : gói DATA từ node — path='direct' (hop 0, node nối thẳng Root) hoặc 'relayed' (hop >= 1)
  local_data : dữ liệu cục bộ của Root (giả, cờ FAKE) — không bao giờ tính vào PDR
  stats      : gói STATS từ node (tự báo số gói đã tạo, retry, RTT TB, dòng TB, RSSI...)
  events     : mọi dòng log khác của Root (BOOT, CONNECTED, ROUTE_CHANGE, ROOT_STATS...), giữ nguyên JSON

host_ts = giờ máy tính lúc nhận dòng (ISO, ms). t_ms = đồng hồ của Root (reset khi Root khởi động lại),
nên mọi phép tính thời gian giữa các sự kiện dùng host_ts.
"""
import datetime as dt
import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT, ended_at TEXT,
    source TEXT,            -- 'serial' (đọc trực tiếp Root) hoặc 'replay' (nạp lại từ file log)
    note TEXT,
    topology TEXT, power TEXT, fw TEXT
);
CREATE TABLE IF NOT EXISTS data (
    run_id TEXT, host_ts TEXT, t_ms INTEGER,
    node TEXT, boot INTEGER, seq INTEGER, hop INTEGER, ttl INTEGER, flags INTEGER,
    parent TEXT, via TEXT, ldr INTEGER, i_ma_x10 INTEGER, vbat_mv INTEGER,
    chk TEXT, ack INTEGER,
    path TEXT,              -- 'direct' | 'relayed'
    fake INTEGER, retry INTEGER
);
CREATE INDEX IF NOT EXISTS data_run ON data(run_id, node, boot, seq);
CREATE TABLE IF NOT EXISTS local_data (
    run_id TEXT, host_ts TEXT, t_ms INTEGER, seq INTEGER, ldr INTEGER, flags INTEGER
);
CREATE TABLE IF NOT EXISTS stats (
    run_id TEXT, host_ts TEXT, t_ms INTEGER,
    node TEXT, via TEXT, boot INTEGER, gen INTEGER, retries INTEGER, qfull INTEGER,
    parent_lost INTEGER, rssi INTEGER, rtt_avg_ms INTEGER, i_avg_x10 INTEGER
);
CREATE INDEX IF NOT EXISTS stats_run ON stats(run_id, node, boot);
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT, host_ts TEXT, t_ms INTEGER, type TEXT, node TEXT, json TEXT
);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, type);
"""

NO_CURRENT = -32768  # STATS.i_avg_x10 khi node không có INA219


def now_iso():
    return dt.datetime.now().isoformat(timespec="milliseconds")


def connect(path):
    # WAL + timeout: analyze.py / gateway khác đọc ghi cùng lúc thì chờ khóa thay vì báo "database is locked"
    db = sqlite3.connect(path, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def start_run(db, run_id, source, note=""):
    """Tạo run mới. Run đã có thì xóa dữ liệu cũ của nó (chạy lại cùng tên = ghi đè)."""
    for table in ("data", "local_data", "stats", "events", "runs"):
        db.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
    db.execute("INSERT INTO runs (run_id, started_at, source, note) VALUES (?, ?, ?, ?)",
               (run_id, now_iso(), source, note))
    db.commit()


def end_run(db, run_id, ended_at=None):
    db.execute("UPDATE runs SET ended_at = ? WHERE run_id = ?", (ended_at or now_iso(), run_id))
    db.commit()


def store(db, run_id, host_ts, e):
    """Ghi một sự kiện JSON của Root vào đúng bảng. Trả về loại: 'data' | 'local' | 'stats' | 'event'."""
    typ = e["type"]
    t = e.get("t")
    if typ == "DATA_RX":
        flags = int(e.get("flags", 0))
        db.execute(
            "INSERT INTO data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, host_ts, t, e["node"], e["boot"], e["seq"], e["hop"], e["ttl"], flags, e.get("parent"),
             e.get("via"), e.get("ldr"), e.get("i_ma_x10"), e.get("vbat_mv"), e.get("check"), e.get("ack"),
             "direct" if e["hop"] == 0 else "relayed", flags & 1, 1 if flags & 2 else 0))
        return "data"
    if typ == "LOCAL_DATA":
        db.execute("INSERT INTO local_data VALUES (?,?,?,?,?,?)",
                   (run_id, host_ts, t, e.get("seq"), e.get("ldr"), e.get("flags")))
        return "local"
    if typ == "STATS_RX":
        db.execute(
            "INSERT INTO stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, host_ts, t, e["node"], e.get("via"), e["boot"], e["gen"], e.get("retries"), e.get("qfull"),
             e.get("parent_lost"), e.get("rssi"), e.get("rtt_avg_ms"), e.get("i_avg_x10")))
        return "stats"
    if typ == "BOOT" and e.get("node") == "R":
        db.execute("UPDATE runs SET topology = ?, power = ?, fw = ? WHERE run_id = ?",
                   (f"{e.get('topology')} {e.get('order')}", e.get("power"), e.get("fw"), run_id))
    elif typ == "ROOT_SUMMARY":  # có fw kể cả khi không bắt được dòng BOOT
        db.execute("UPDATE runs SET fw = ? WHERE run_id = ? AND fw IS NULL", (e.get("fw"), run_id))
    db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
               (run_id, host_ts, t, typ, e.get("node"), json.dumps(e, separators=(",", ":"))))
    return "event"


def parse_line(raw):
    """Một dòng Root in ra -> dict, hoặc None nếu không phải JSON hợp lệ của firmware."""
    raw = raw.strip()
    if not raw.startswith("{"):
        return None
    try:
        e = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(e, dict) or "type" not in e or "t" not in e:
        return None
    return e
