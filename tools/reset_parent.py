"""Reset cha hiện tại của một node (đọc dòng PARENT mới nhất trong log đang ghi), lặp nhiều lần.

Dùng cho kiểm tra đổi tuyến (DIAMOND, E6): logcap.py phải đang chạy cho cùng thư mục run.

    python tools/reset_parent.py m3-diamond-reroute --node C --times 3 --wait 45 --first 60
      --first: chờ trước lần reset đầu (s); --wait: chờ giữa các lần (s)
Reset bằng `picotool reboot -f` (board khởi động lại ngay, như tắt/bật nguồn nhanh).
--cmd u: thay vì reset, gửi lệnh 'u' cho cha qua logcap (cha tự cắt liên kết lên ông và
         ngừng quảng bá 15 s, vẫn sống) -> kiểm tra đổi tuyến khi cha mất đường lên Root.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import time

from boards import BOARDS
from flash import PICOTOOL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def current_parent(log_path):
    parent = None
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n").partition("\t")[2]
            if '"PARENT"' not in raw:
                continue
            try:
                parent = json.loads(raw)["parent"]
            except ValueError:
                pass
    return parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--node", default="C")
    ap.add_argument("--times", type=int, default=3)
    ap.add_argument("--first", type=float, default=60)
    ap.add_argument("--wait", type=float, default=45)
    ap.add_argument("--cmd")
    a = ap.parse_args()
    log = os.path.join(ROOT, "experiments", a.run, f"{a.node.upper()}.log")
    time.sleep(a.first)
    for i in range(a.times):
        p = current_parent(log)
        if p not in BOARDS or p == "R":
            print(f"[{i + 1}] parent of {a.node} = {p!r}, skip")
        elif a.cmd:
            with open(os.path.join(os.path.dirname(log), f"_send_{p}.txt"), "w", encoding="utf-8") as f:
                f.write(a.cmd)
            stamp = dt.datetime.now().isoformat(timespec="milliseconds")
            print(f"[{i + 1}] {stamp} send {a.cmd!r} to {p} (parent of {a.node})", flush=True)
        else:
            r = subprocess.run([PICOTOOL, "reboot", "-f", "--ser", BOARDS[p]], capture_output=True, text=True)
            stamp = dt.datetime.now().isoformat(timespec="milliseconds")
            print(f"[{i + 1}] {stamp} reset {p} (parent of {a.node}): rc={r.returncode}", flush=True)
        if i + 1 < a.times:
            time.sleep(a.wait)


if __name__ == "__main__":
    main()
