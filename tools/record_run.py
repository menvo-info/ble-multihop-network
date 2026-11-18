"""record_run.py — chụp ảnh + quay video timelapse trang dashboard cho các run thực nghiệm (minh chứng cho báo cáo).

    python tools/record_run.py E1 E2                 # ghi các run đã xong
    python tools/record_run.py --watch --since 2026-11-12T23:00 --until-file <log> --until-text "XONG: E1 --topo"

Với mỗi run, ghi vào experiments/<run>/analysis/:
  dashboard.png  — toàn trang, chế độ "Toàn bộ"
  dashboard.mp4  — phát lại cả run (N khung, mỗi khung = trạng thái tại thời điểm t, cửa sổ 5 phút)
Cần dashboard.py đang chạy (http://localhost:8000), Edge và ffmpeg. Edge chạy ưu tiên thấp để không giành CPU
với gateway khi thực nghiệm khác đang chạy.
"""
import argparse
import glob
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "gateway", "wsn.db")
URL = "http://localhost:8000/"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
LOW = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    hits = glob.glob(os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe"))
    return hits[0] if hits else None


def shot(url, out, profile, size="1400,1500", budget=2500):
    if os.path.exists(out):
        os.remove(out)
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size}",
           f"--virtual-time-budget={budget}", f"--screenshot={out}", f"--user-data-dir={profile}", url]
    try:
        subprocess.run(cmd, timeout=60, capture_output=True, creationflags=LOW)
    except subprocess.TimeoutExpired:
        pass
    # msedge.exe trả về ngay, ảnh được ghi vài giây sau -> đợi file xuất hiện và kích thước đứng yên
    last, t_end = -1, time.time() + 45
    while time.time() < t_end:
        if os.path.exists(out):
            size = os.path.getsize(out)
            if size > 0 and size == last:
                return True
            last = size
        time.sleep(0.7)
    return os.path.exists(out)


def run_info(run_id):
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    r = db.execute("SELECT started_at, ended_at FROM runs WHERE run_id=?", (run_id,)).fetchone()
    db.close()
    return r


def record(run_id, frames, fps, ffmpeg):
    info = run_info(run_id)
    if not info or not info[1]:
        print(f"{run_id}: chưa xong / không có, bỏ qua")
        return False
    import datetime as dt
    dur = (dt.datetime.fromisoformat(info[1]) - dt.datetime.fromisoformat(info[0])).total_seconds()
    out_dir = os.path.join(ROOT, "experiments", run_id, "analysis")
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=f"rec-{run_id}-")
    profile = os.path.join(tmp, "profile")
    t0 = time.time()
    ok = shot(f"{URL}?run={run_id}&nolive=1", os.path.join(out_dir, "dashboard.png"), profile, "1400,1700")
    n = 0
    for i in range(frames):
        t = dur * (i + 1) / frames
        if shot(f"{URL}?run={run_id}&nolive=1&replay=1&pause=1&win=300&from={t:.1f}",
                os.path.join(tmp, f"f{n:04d}.png"), f"{profile}{i}"):
            n += 1
    if n and ffmpeg:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "f%04d.png"),
                        "-vf", "scale=1280:-2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        os.path.join(out_dir, "dashboard.mp4")], creationflags=LOW)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{run_id}: ảnh {'OK' if ok else 'LỖI'}, video {n}/{frames} khung, {time.time() - t0:.0f} s", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--fps", type=int, default=6)
    ap.add_argument("--watch", action="store_true", help="đợi các run mới xong rồi ghi, tới khi gặp until-text")
    ap.add_argument("--since", default="")
    ap.add_argument("--until-file", default="")
    ap.add_argument("--until-text", default="")
    a = ap.parse_args()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("Không thấy ffmpeg -> chỉ chụp ảnh")
    for r in a.runs:
        record(r, a.frames, a.fps, ffmpeg)
    if not a.watch:
        return
    done = set(a.runs)
    while True:
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
        ready = [r[0] for r in db.execute("SELECT run_id FROM runs WHERE ended_at IS NOT NULL AND started_at >= ? "
                                          "ORDER BY started_at", (a.since,))]
        db.close()
        for r in ready:
            if r not in done:
                done.add(r)
                time.sleep(20)   # để analyze.py của run đó ghi xong
                record(r, a.frames, a.fps, ffmpeg)
        finished = False
        if a.until_file and os.path.exists(a.until_file):
            with open(a.until_file, encoding="utf-8", errors="replace") as f:
                finished = a.until_text in f.read()
        if finished and all(r in done for r in ready):
            break
        time.sleep(60)
    print("Xong ghi hình.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
