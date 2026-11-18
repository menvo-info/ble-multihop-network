"""gateway.py — đọc log JSON của Root qua USB -> kiểm tra -> SQLite -> MQTT.

    python gateway/gateway.py E1-pair --minutes 30 --note "PAIR A FAST, ban"   # đọc Root trực tiếp
    python gateway/gateway.py m2-chain-30min --replay                          # nạp lại experiments/<run>/R.log

Đọc trực tiếp: tự tìm cổng COM của Root theo serial (tools/boards.py), hoặc --port COMx. Mỗi dòng nhận được
cũng được ghi nguyên văn vào experiments/<run>/R.log (cùng định dạng tools/logcap.py: "<giờ máy>\\t<dòng>"),
nên tools/summarize.py vẫn đọc được. Khi gateway giữ cổng Root thì chạy logcap.py chỉ cho node:
    python tools/logcap.py E1-pair --minutes 30 --boards A B C

MQTT (Mosquitto local, mặc định localhost:1883; --no-mqtt để tắt):
    wsn/<node>/data   gói DATA (node = A/B/C), thêm "path": direct|relayed
    wsn/<node>/stats  gói STATS
    wsn/R/local       dữ liệu cục bộ (giả) của Root
    wsn/event         sự kiện khác (kết nối, đổi tuyến, ROOT_STATS...)
Không kết nối được broker thì vẫn ghi SQLite và báo một dòng cảnh báo (không dừng thu dữ liệu).
"""
import argparse
import json
import os
import sys
import time

import wsn_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DEFAULT_DB = os.path.join(ROOT, "gateway", "wsn.db")


class Mqtt:
    def __init__(self, host, port, enabled):
        self.client = None
        if not enabled:
            return
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wsn-gateway")
            self.client.connect(host, port, keepalive=30)
            self.client.loop_start()
            print(f"MQTT: {host}:{port}")
        except Exception as ex:  # broker tắt, chưa cài paho...
            print(f"MQTT disabled: {ex}")
            self.client = None

    def publish(self, kind, e):
        if not self.client:
            return
        node = e.get("node", "?")
        if kind == "data":
            topic = f"wsn/{node}/data"
            e = dict(e, path="direct" if e.get("hop") == 0 else "relayed")
        elif kind == "stats":
            topic = f"wsn/{node}/stats"
        elif kind == "local":
            topic = "wsn/R/local"
        else:
            topic = "wsn/event"
        self.client.publish(topic, json.dumps(e, separators=(",", ":")), qos=0)

    def close(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


class Counter:
    def __init__(self):
        self.n = {"data": 0, "local": 0, "stats": 0, "event": 0, "bad": 0}

    def __str__(self):
        return " ".join(f"{k}={v}" for k, v in self.n.items())


def handle(db, mq, run_id, host_ts, raw, cnt):
    e = wsn_db.parse_line(raw)
    if e is None:
        if raw.strip().startswith("{"):
            cnt.n["bad"] += 1  # JSON hỏng (vd. dòng bị cắt lúc USB mở cổng)
        return
    kind = wsn_db.store(db, run_id, host_ts, e)
    cnt.n[kind] += 1
    mq.publish(kind, e)


def replay(db, mq, run_id, path):
    cnt = Counter()
    first = last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            host_ts, _, raw = line.rstrip("\n").partition("\t")
            if raw.startswith("#"):
                continue
            handle(db, mq, run_id, host_ts, raw, cnt)
            first = first or host_ts
            last = host_ts
    db.execute("UPDATE runs SET started_at = ? WHERE run_id = ?", (first, run_id))
    db.commit()
    return cnt, last


def live(db, mq, run_id, port, minutes, raw_path):
    import serial
    from boards import find_ports

    cnt = Counter()
    end = time.time() + minutes * 60 if minutes else None
    next_report = time.time() + 60
    next_commit = time.time() + 2
    ser = None
    send_path = os.path.join(os.path.dirname(raw_path), "_send_R.txt")
    with open(raw_path, "a", encoding="utf-8", newline="\n") as raw_log:
        while end is None or time.time() < end:
            if ser is None:
                p = port or find_ports().get("R")
                if not p:
                    time.sleep(0.5)
                    continue
                try:
                    ser = serial.Serial(p, 115200, timeout=0.5)
                    ser.dtr = True  # stdio USB của Pico chỉ gửi khi DTR bật
                    raw_log.write(f"{wsn_db.now_iso()}\t#PORT_OPEN {p}\n")
                except serial.SerialException:
                    ser = None
                    time.sleep(0.5)
                    continue
            try:
                if os.path.exists(send_path):  # lệnh test cho Root (vd. "ackdrop 20"), xem tools/logcap.py
                    with open(send_path, encoding="utf-8") as sf:
                        cmd = sf.read().strip()
                    os.remove(send_path)
                    ser.write((cmd + "\n").encode())
                    raw_log.write(f"{wsn_db.now_iso()}\t#SENT {cmd}\n")
                b = ser.readline()
            except (serial.SerialException, OSError):
                raw_log.write(f"{wsn_db.now_iso()}\t#PORT_LOST\n")
                raw_log.flush()
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                continue
            now = time.time()
            if b:
                line = b.decode("utf-8", "replace").rstrip("\r\n")
                host_ts = wsn_db.now_iso()
                raw_log.write(f"{host_ts}\t{line}\n")
                raw_log.flush()
                handle(db, mq, run_id, host_ts, line, cnt)
            if now >= next_commit:
                db.commit()
                next_commit = now + 2
            if now >= next_report:
                print(f"[{time.strftime('%H:%M:%S')}] {cnt}", flush=True)
                next_report = now + 60
    if ser:
        ser.close()
    db.commit()
    return cnt


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--minutes", type=float, default=0, help="0 = chạy tới khi Ctrl+C")
    ap.add_argument("--port")
    ap.add_argument("--replay", nargs="?", const="", metavar="R.log",
                    help="nạp lại từ file (mặc định experiments/<run>/R.log)")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--note", default="")
    ap.add_argument("--topology", help='vd. "CHAIN CBA" (dòng BOOT của Root sẽ ghi đè nếu bắt được)')
    ap.add_argument("--power", help="FAST | LOW_POWER")
    ap.add_argument("--no-mqtt", action="store_true")
    ap.add_argument("--replay-mqtt", action="store_true", help="khi --replay: vẫn publish MQTT")
    ap.add_argument("--mqtt-host", default="localhost")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    a = ap.parse_args()

    db = wsn_db.connect(a.db)
    if a.replay is not None:
        path = a.replay or os.path.join(ROOT, "experiments", a.run, "R.log")
        mq = Mqtt(a.mqtt_host, a.mqtt_port, a.replay_mqtt)  # phát lại: mặc định không publish
        wsn_db.start_run(db, a.run, "replay", a.note or f"replay {os.path.relpath(path, ROOT)}")
        cnt, last = replay(db, mq, a.run, path)
        wsn_db.end_run(db, a.run, last)
    else:
        mq = Mqtt(a.mqtt_host, a.mqtt_port, not a.no_mqtt)
        out = os.path.join(ROOT, "experiments", a.run)
        os.makedirs(out, exist_ok=True)
        wsn_db.start_run(db, a.run, "serial", a.note)
        if a.topology or a.power:
            db.execute("UPDATE runs SET topology = ?, power = ? WHERE run_id = ?", (a.topology, a.power, a.run))
            db.commit()
        print(f"Gateway run={a.run} db={a.db} raw={os.path.join(out, 'R.log')}")
        try:
            cnt = live(db, mq, a.run, a.port, a.minutes, os.path.join(out, "R.log"))
        except KeyboardInterrupt:
            cnt = None
            db.commit()
        wsn_db.end_run(db, a.run)
    mq.close()
    print(f"run {a.run}: {cnt if cnt else 'stopped'}")


if __name__ == "__main__":
    main()
