"""exp.py — chạy một thực nghiệm E1–E8 trọn gói (xem docs/HUONG_DAN_THUC_NGHIEM.md).

    python tools/exp.py E1                        # PAIR A, 30 phút
    python tools/exp.py E2                        # CHAIN CBA, 30 phút (RTT theo số hop)
    python tools/exp.py E3                        # CHAIN CBA: nhắc bạn tắt công tắc B 5 s, 3 lần
    python tools/exp.py E3 --auto                 # ... hoặc tự reset B bằng picotool (không cần tay)
    python tools/exp.py E4 --ackdrop 20           # CHAIN CBA: Root cố ý bỏ 20% ACK -> retry, gói trùng
    python tools/exp.py E5 --period 100           # CHAIN CBA: A, B, C tạo DATA mỗi 100 ms -> queue đầy
    python tools/exp.py E6                        # DIAMOND CAB: reset cha hiện tại của C 6 lần
    python tools/exp.py E6 --cmd u                # ... hoặc cha tự cắt đường lên Root (node vẫn sống)
    python tools/exp.py E7 --power FAST           # CHAIN CBA, 20 phút, BẬT PIN; rồi chạy lại với LOW_POWER
    python tools/exp.py E8 --topo DIAMOND --minutes 60 --no-flash   # thực địa: chỉ Root cắm laptop

Tùy chọn chung: --minutes N, --tag X (thêm vào tên run), --order CBA, --no-flash (giữ fw đang chạy),
--dry-run (chỉ in kế hoạch). Tên run = <E>[-tham số][-tag], log ở experiments/<run>/, kết quả ở
experiments/<run>/analysis/ (metrics.md + biểu đồ). Gateway giữ cổng Root (SQLite + MQTT + R.log), logcap
ghi log các node. So sánh: python gateway/analyze.py --compare E7-FAST E7-LOW_POWER
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time

from boards import BOARDS, find_ports
from flash import PICOTOOL, flash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
SETTLE_S = 60  # chờ mạng ổn định sau khi nạp trước thao tác đầu tiên

# Mặc định của từng thực nghiệm: topology, thứ tự, chế độ, số phút, thao tác
PRESETS = {
    "E1": dict(topo="PAIR", order="A", power="FAST", minutes=31, what="1 hop, 30 phút: PDR, ACK RTT"),
    "E2": dict(topo="CHAIN", order="CBA", power="FAST", minutes=31, what="1-3 hop, 30 phút: PDR, RTT theo số hop"),
    "E3": dict(topo="CHAIN", order="CBA", power="FAST", minutes=10, what="tắt B 5 s, 3 lần: kết nối lại, mất gói, retry"),
    "E4": dict(topo="CHAIN", order="CBA", power="FAST", minutes=8, what="Root bỏ ACK có kiểm soát: retry, gói trùng bị lọc"),
    "E5": dict(topo="CHAIN", order="CBA", power="FAST", minutes=6, what="tăng tốc độ gửi: queue đầy, gói bỏ"),
    "E6": dict(topo="DIAMOND", order="CAB", power="FAST", minutes=10, what="mất cha của C, 6 lần: thời gian đổi tuyến"),
    "E7": dict(topo="CHAIN", order="CBA", power="FAST", minutes=21, what="FAST vs LOW_POWER (bật pin): dòng TB, PDR, RTT"),
    "E8": dict(topo="DIAMOND", order="CAB", power="FAST", minutes=60, what="thực địa: PDR, RSSI, đổi tuyến"),
    "E9": dict(topo="MESH", order="ABC", power="FAST", minutes=13,
               what="MESH tự chọn đường: Root chặn node (giả lập ở xa) -> node đi vòng qua node khác"),
}


def stamp():
    return dt.datetime.now().strftime("%H:%M:%S")


def say(msg):
    print(f"[{stamp()}] {msg}", flush=True)


def ask_hand(msg):
    """Thao tác tay: in nổi bật + chuông."""
    print(f"\a\n[{stamp()}] >>> {msg}\n", flush=True)


def send(run, board, cmd):
    with open(os.path.join(ROOT, "experiments", run, f"_send_{board}.txt"), "w", encoding="utf-8") as f:
        f.write(cmd)
    say(f"lệnh '{cmd}' -> {board}")


def reboot(board):
    r = subprocess.run([PICOTOOL, "reboot", "-f", "--ser", BOARDS[board]], capture_output=True, text=True)
    say(f"reset {board} (picotool) rc={r.returncode}")


def wait_until(t_end):
    while time.time() < t_end:
        time.sleep(min(30, max(0.2, t_end - time.time())))


def actions_for(a, run):
    """Danh sách (giây sau khi ổn định, mô tả, hàm) cho từng thực nghiệm."""
    acts = []
    if a.exp == "E3":
        for k in range(3):
            at = 60 + k * 150
            if a.auto:
                acts.append((at, "reset B", lambda: reboot("B")))
            else:
                acts.append((at, "TẮT công tắc B", lambda: ask_hand("TẮT công tắc nguồn của B NGAY (B chạy pin, rút USB)")))
                acts.append((at + 5, "BẬT lại B", lambda: ask_hand("BẬT lại công tắc B NGAY")))
    elif a.exp == "E4":
        acts.append((60, f"ackdrop {a.ackdrop}", lambda: send(run, "R", f"ackdrop {a.ackdrop}")))
        acts.append((a.minutes * 60 - SETTLE_S - 90, "ackdrop 0", lambda: send(run, "R", "ackdrop 0")))
    elif a.exp == "E5":
        def set_all(p):
            for n in "ABC":
                send(run, n, f"period {p}")
        acts.append((60, f"period {a.period}", lambda: set_all(a.period)))
        acts.append((a.minutes * 60 - SETTLE_S - 60, "period 1000", lambda: set_all(1000)))
    elif a.exp == "E6":
        def act():
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from reset_parent import current_parent
            p = current_parent(os.path.join(ROOT, "experiments", run, "C.log"))
            if p not in ("A", "B"):
                say(f"cha của C = {p!r}, bỏ qua lần này")
            elif a.cmd:
                send(run, p, a.cmd)
            else:
                reboot(p)
        for k in range(6):
            acts.append((30 + k * 75, "mất cha của C", act))
    elif a.exp == "E9":
        # deny X: Root coi như không nghe thấy X -> X phải nhờ node khác chuyển lên. Mỗi bước kiểm tra một tình huống.
        steps = [(60, "deny A"),     # A mất Root -> đi qua B hoặc C
                 (180, "deny AB"),   # A, B mất Root -> cả hai đi qua C
                 (300, "deny -"),    # Root nghe lại hết (node đang có cha thì giữ đường cũ)
                 (330, None),        # reset C (đang là relay của A, B) -> A, B phải tìm đường mới (về Root)
                 (450, "deny BC"),   # B, C mất Root -> đi qua A
                 (600, "deny -")]
        for at, cmd in steps:
            if cmd:
                acts.append((at, cmd, lambda c=cmd: send(run, "R", c)))
            else:
                acts.append((at, "reset C", lambda: reboot("C")))
    return acts


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exp", choices=sorted(PRESETS))
    ap.add_argument("--minutes", type=float)
    ap.add_argument("--topo")
    ap.add_argument("--order")
    ap.add_argument("--power", choices=["FAST", "LOW_POWER"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--auto", action="store_true", help="E3: reset B bằng picotool thay vì tắt công tắc")
    ap.add_argument("--ackdrop", type=int, default=20, help="E4: %% ACK Root cố ý bỏ")
    ap.add_argument("--period", type=int, default=100, help="E5: chu kỳ DATA (ms)")
    ap.add_argument("--cmd", help="E6: gửi lệnh này (vd. u) cho cha của C thay vì reset")
    ap.add_argument("--no-flash", action="store_true")
    ap.add_argument("--no-nodes", action="store_true", help="không ghi log node (thực địa)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    p = dict(PRESETS[a.exp])
    a.topo = a.topo or p["topo"]
    a.order = a.order or p["order"]
    a.power = a.power or p["power"]
    a.minutes = a.minutes or p["minutes"]
    if a.exp == "E8":
        a.no_nodes = True

    name = a.exp
    if a.exp == "E3" and a.auto:
        name += "-auto"
    if a.exp == "E4":
        name += f"-ack{a.ackdrop}"
    if a.exp == "E5":
        name += f"-p{a.period}"
    if a.exp == "E6" and a.cmd:
        name += f"-{a.cmd}"
    if a.exp == "E7":
        name += f"-{a.power}"
    if a.tag:
        name += f"-{a.tag}"
    uf2 = os.path.join(ROOT, "pico2w-wsn", f"build-{a.topo}-{a.order}-{a.power}", "pico2w-wsn.uf2")
    acts = actions_for(a, name)
    note = f"{a.exp}: {p['what']} | {a.topo} {a.order} {a.power}"

    print(f"== {name}: {note}, {a.minutes} phút")
    print(f"   fw: {os.path.relpath(uf2, ROOT)} ({'giữ fw đang chạy' if a.no_flash else 'build + nạp'})")
    for at, desc, _ in acts:
        print(f"   +{SETTLE_S + at:>4.0f} s: {desc}")
    if a.exp == "E7":
        print("   CẦN: công tắc pin A, B (và C nếu có mạch) BẬT trong suốt lần chạy.")
    if a.exp == "E3" and not a.auto:
        print("   CẦN: B chạy pin, công tắc trong tầm tay; script sẽ nhắc lúc tắt / bật.")
    if a.dry_run:
        return

    ports = find_ports()
    if "R" not in ports:
        sys.exit("Không thấy Root (R) trên USB")
    if not a.no_flash:
        r = subprocess.run(["bash", os.path.join(ROOT, "tools", "build.sh"), a.topo, a.order, a.power], cwd=ROOT)
        if r.returncode:
            sys.exit("build lỗi")
    out = os.path.join(ROOT, "experiments", name)
    if os.path.exists(os.path.join(out, "R.log")):
        sys.exit(f"experiments/{name}/ đã có log — đặt --tag khác (không ghi đè log gốc)")
    os.makedirs(out, exist_ok=True)

    procs = [subprocess.Popen([PY, os.path.join(ROOT, "gateway", "gateway.py"), name, "--minutes", str(a.minutes),
                               "--note", note, "--topology", f"{a.topo} {a.order}", "--power", a.power], cwd=ROOT,
                              stdout=open(os.path.join(out, "_gateway.txt"), "w", encoding="utf-8"),
                              stderr=subprocess.STDOUT)]
    nodes = [n for n in "ABC" if n in ports] if not a.no_nodes else []
    if nodes:
        procs.append(subprocess.Popen([PY, os.path.join(ROOT, "tools", "logcap.py"), name, "--minutes", str(a.minutes),
                                       "--boards", *nodes], cwd=ROOT,
                                      stdout=open(os.path.join(out, "_logcap.txt"), "w", encoding="utf-8"),
                                      stderr=subprocess.STDOUT))
    t_start = time.time()
    time.sleep(5)
    if procs[0].poll() is not None:  # gateway chết ngay (cổng Root bận, DB lỗi...)
        for pr in procs[1:]:
            pr.kill()
        with open(os.path.join(out, "_gateway.txt"), encoding="utf-8") as f:
            print(f.read())
        sys.exit("gateway dừng ngay khi khởi động — xem lỗi ở trên")
    if not a.no_flash:
        say("nạp firmware")
        present = [b for b in BOARDS if b in find_ports()]
        missing = [b for b in BOARDS if b not in present]
        if missing:
            say(f"không cắm USB: {missing} — các board này phải đang chạy sẵn {os.path.relpath(uf2, ROOT)}")
        flash(uf2, present)
    t0 = time.time() + SETTLE_S
    say(f"chờ ổn định {SETTLE_S} s")
    for at, desc, fn in acts:
        wait_until(t0 + at)
        fn()
    t_end = t_start + a.minutes * 60 + 5
    say(f"chờ hết thời gian (tới {dt.datetime.fromtimestamp(t_end).strftime('%H:%M:%S')})")
    for pr in procs:
        pr.wait(timeout=max(10, t_end - time.time() + 30))
    say("phân tích")
    subprocess.run([PY, os.path.join(ROOT, "gateway", "analyze.py"), name], cwd=ROOT)
    print(f"Xong: experiments/{name}/analysis/metrics.md")


if __name__ == "__main__":
    main()
