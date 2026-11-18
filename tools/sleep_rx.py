"""sleep_rx.py — máy thu cho firmware tools/sleepnode (node lá ngủ sâu, chỉ phát quảng bá BLE).

    python tools/sleep_rx.py --minutes 20 --out experiments/S1-PSTATE-10s
    python tools/sleep_rx.py --minutes 20 --out experiments/S1-PSTATE-10s --i-sleep-ua 250 --mah 2000

Dùng Bluetooth của laptop (thư viện bleak). Mỗi lần node thức sẽ phát cùng một gói ~15 lần; máy thu lọc trùng theo
(node, boot, seq) và đếm số bản sao nhận được (biên an toàn: càng nhiều bản sao thì càng khó mất gói).
Gói chứa số đo của LẦN THỨC TRƯỚC (thời gian thức, dòng TB lúc thức do INA219 đo) nên có thể tính dòng trung bình:
    I_TB = (I_thức × T_thức + I_ngủ × (T_chu_kỳ − T_thức)) / T_chu_kỳ
I_ngủ phải đo bằng đồng hồ vạn năng (thang mA/uA, mắc nối tiếp pin) vì lúc ngủ chip không đọc được INA219.
Kết quả: <out>/packets.csv (mỗi gói một dòng) và <out>/summary.md.
"""
import argparse
import asyncio
import csv
import os
import statistics
import struct
import sys
import time

from bleak import BleakScanner

COMPANY = 0xFFFF
MODES = {1: "PSTATE", 2: "DORMANT", 3: "AWAKE"}


REASONS = {0: "luôn gửi", 1: "đổi dữ liệu", 2: "nhịp tim"}


def parse(payload: bytes):
    # v1: 21 byte. v2 (chu kỳ tự thích nghi): thêm lý do gửi (4 bit cao của byte mode) + số lần thức chỉ đo.
    if len(payload) < 21 or payload[:2] != b"SL" or payload[2] not in (1, 2):
        return None
    node, boot, seq, ldr, vbat, i_prev, aw_prev, mode, period = struct.unpack_from("<cHIHHhHBH", payload, 3)
    reason, skipped = mode >> 4, 0
    if payload[2] == 2 and len(payload) >= 23:
        skipped = struct.unpack_from("<H", payload, 21)[0]
    return {"node": node.decode(errors="replace"), "boot": boot, "seq": seq, "ldr": ldr, "vbat_mv": vbat,
            "i_prev_ma": i_prev / 10, "awake_prev_ms": aw_prev, "mode": MODES.get(mode & 0x0F, mode & 0x0F),
            "period_s": period / 10, "reason": REASONS.get(reason, reason), "skipped": skipped}


def summarize(pk, copies, a):
    lines = ["# Kết quả node ngủ sâu (sleepnode)", ""]
    nodes = sorted({p["node"] for p in pk})
    for n in nodes:
        rows = [p for p in pk if p["node"] == n]
        by_boot = {}
        for p in rows:
            by_boot.setdefault(p["boot"], set()).add(p["seq"])
        got = sum(len(s) for s in by_boot.values())
        span = sum(max(s) - min(s) + 1 for s in by_boot.values())
        cp = [copies[(p["node"], p["boot"], p["seq"])] for p in rows]
        aw = [p["awake_prev_ms"] for p in rows if p["awake_prev_ms"]]
        ia = [p["i_prev_ma"] for p in rows if p["awake_prev_ms"] and p["i_prev_ma"] > 0]
        gaps = [b["t"] - x["t"] for x, b in zip(rows, rows[1:])]
        per = rows[-1]["period_s"]
        lines += [f"## Node {n} ({rows[-1]['mode']}, chu kỳ {per:g} s)", "",
                  "| Chỉ số | Giá trị |", "|---|---|",
                  f"| Gói nhận / gói đã phát (PDR) | {got}/{span} = {100 * got / max(span, 1):.2f}% |",
                  f"| Số bản sao nhận được mỗi gói (TB / nhỏ nhất) | {statistics.mean(cp):.1f} / {min(cp)} |",
                  f"| Khoảng cách giữa 2 gói (TB / lớn nhất) | {statistics.mean(gaps) if gaps else 0:.2f} / {max(gaps) if gaps else 0:.2f} s |"]
        if aw:
            lines.append(f"| Thời gian thức mỗi chu kỳ (TB / lớn nhất) | {statistics.mean(aw):.0f} / {max(aw)} ms |")
        if ia:
            lines.append(f"| Dòng TB lúc thức (INA219) | {statistics.mean(ia):.1f} mA |")
        vb = [p["vbat_mv"] for p in rows if p["vbat_mv"]]
        if vb:
            lines.append(f"| Điện áp pin đầu → cuối | {vb[0]} → {vb[-1]} mV |")
        if aw and ia and a.i_sleep_ua is not None:
            t_aw, i_aw, i_sl = statistics.mean(aw) / 1000, statistics.mean(ia), a.i_sleep_ua / 1000
            i_avg = (i_aw * t_aw + i_sl * max(per - t_aw, 0)) / per
            lines += [f"| Dòng ngủ (đo bằng đồng hồ) | {a.i_sleep_ua:g} uA |",
                      f"| **Dòng trung bình ước tính** | **{i_avg:.3f} mA** |",
                      f"| Tuổi thọ pin {a.mah:g} mAh (bỏ qua tự xả, hiệu suất 80%) | {a.mah * 0.8 / i_avg / 24:.0f} ngày |"]
        lines.append("")
    return "\n".join(lines)


async def run(a):
    pk, copies = [], {}
    t0 = time.time()

    def on_adv(dev, adv):
        raw = adv.manufacturer_data.get(COMPANY)
        p = parse(raw) if raw else None
        if not p:
            return
        k = (p["node"], p["boot"], p["seq"])
        copies[k] = copies.get(k, 0) + 1
        if copies[k] > 1:
            return
        p["t"] = round(time.time() - t0, 3)
        p["rssi"] = adv.rssi
        pk.append(p)
        print(f"{p['t']:8.1f}s  {p['node']} boot {p['boot']:5d} seq {p['seq']:5d}  ldr {p['ldr']:4d}  "
              f"vbat {p['vbat_mv']:4d} mV  lần thức trước {p['awake_prev_ms']:5d} ms @ {p['i_prev_ma']:5.1f} mA  "
              f"rssi {adv.rssi}  [{p['reason']}, bỏ qua {p['skipped']} lần đo]", flush=True)

    async with BleakScanner(detection_callback=on_adv):
        try:
            while time.time() - t0 < a.minutes * 60:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    return pk, copies


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--out", default="")
    ap.add_argument("--i-sleep-ua", type=float, default=None, help="dòng lúc ngủ đo bằng đồng hồ vạn năng (uA)")
    ap.add_argument("--mah", type=float, default=2000)
    a = ap.parse_args()
    try:
        pk, copies = asyncio.run(run(a))
    except KeyboardInterrupt:
        print("Dừng sớm: không có tóm tắt (hãy dùng --minutes)")
        return 1
    if not pk:
        print("Không nhận được gói nào (node có đang chạy sleepnode? Bluetooth laptop bật chưa?)")
        return 1
    md = summarize(pk, copies, a)
    print("\n" + md)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "packets.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pk[0].keys()) + ["copies"])
            w.writeheader()
            for p in pk:
                w.writerow({**p, "copies": copies[(p["node"], p["boot"], p["seq"])]})
        with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
            f.write(md + "\n")
        print(f"Đã ghi {a.out}/packets.csv, summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
