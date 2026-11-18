"""Ghi log USB của nhiều board cùng lúc vào experiments/<run>/<board>.log.

Mỗi dòng file log = "<giờ máy tính ISO>\\t<dòng gốc board in ra>" — không sửa nội dung gốc.
Tự mở lại cổng khi board reset / rút cắm (cổng COM biến mất rồi xuất hiện lại).

    python tools/logcap.py m1-pair-30min --minutes 30            # mọi board đang cắm
    python tools/logcap.py test --minutes 2 --boards R A
Kết thúc thì in tóm tắt (tools/summarize.py).

Gửi lệnh test xuống board khi đang ghi (cổng COM đang bị giữ): ghi nội dung vào file
experiments/<run>/_send_<board>.txt (mỗi lệnh một dòng) — logcap gửi đi, ghi dòng "#SENT ..." vào log rồi xóa file.
"""
import argparse
import datetime as dt
import os
import threading
import time

import serial

from boards import find_ports

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def capture(name, path, stop, counts):
    ser = None
    send_path = os.path.join(os.path.dirname(path), f"_send_{name}.txt")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        while not stop.is_set():
            if ser is None:
                port = find_ports().get(name)
                if not port:
                    time.sleep(0.5)
                    continue
                try:
                    ser = serial.Serial(port, 115200, timeout=0.5)
                    ser.dtr = True  # stdio USB của Pico chỉ gửi khi DTR bật
                    f.write(f"{dt.datetime.now().isoformat(timespec='milliseconds')}\t#PORT_OPEN {port}\n")
                except serial.SerialException:
                    ser = None
                    time.sleep(0.5)
                    continue
            try:
                if os.path.exists(send_path):
                    with open(send_path, encoding="utf-8") as sf:
                        cmd = sf.read().strip()
                    os.remove(send_path)
                    ser.write((cmd + "\n").encode())  # firmware đọc lệnh theo dòng
                    f.write(f"{dt.datetime.now().isoformat(timespec='milliseconds')}\t#SENT {cmd}\n")
                raw = ser.readline()
            except (serial.SerialException, OSError):
                f.write(f"{dt.datetime.now().isoformat(timespec='milliseconds')}\t#PORT_LOST\n")
                f.flush()
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                continue
            if not raw:
                continue
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            f.write(f"{dt.datetime.now().isoformat(timespec='milliseconds')}\t{line}\n")
            f.flush()
            counts[name] += 1
    if ser:
        ser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--minutes", type=float, default=1.0)
    ap.add_argument("--boards", nargs="*")
    a = ap.parse_args()

    names = [b.upper() for b in a.boards] if a.boards else sorted(find_ports())
    out = os.path.join(ROOT, "experiments", a.run)
    os.makedirs(out, exist_ok=True)
    stop = threading.Event()
    counts = {n: 0 for n in names}
    threads = [threading.Thread(target=capture, args=(n, os.path.join(out, f"{n}.log"), stop, counts), daemon=True)
               for n in names]
    for t in threads:
        t.start()
    print(f"Logging {names} -> {out} for {a.minutes} min")
    end = time.time() + a.minutes * 60
    try:
        while time.time() < end:
            time.sleep(min(60, max(0.1, end - time.time())))
            print(f"[{time.strftime('%H:%M:%S')}] lines: {counts}", flush=True)
    except KeyboardInterrupt:
        pass
    stop.set()
    for t in threads:
        t.join(timeout=2)

    import summarize
    summarize.summarize(out)


if __name__ == "__main__":
    main()
