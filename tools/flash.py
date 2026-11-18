"""Nạp một file UF2 vào các board qua USB (picotool -f, không cần nhấn BOOTSEL).

    python tools/flash.py pico2w-wsn/build-PAIR-A-FAST/pico2w-wsn.uf2            # cả 4 board
    python tools/flash.py <uf2> R A                                               # chỉ R và A
"""
import os
import subprocess
import sys

from boards import BOARDS

PICOTOOL = os.path.expanduser("~/.pico-sdk/picotool/2.3.1/picotool/picotool.exe")


def flash(uf2, names):
    ok = True
    for name in names:
        cmd = [PICOTOOL, "load", "-v", "-x", uf2, "--ser", BOARDS[name], "-f"]  # chọn thiết bị phải đứng sau tên file
        r = subprocess.run(cmd, capture_output=True, text=True)
        good = r.returncode == 0
        ok &= good
        last = (r.stdout + r.stderr).strip().splitlines()
        print(f"{name}: {'OK' if good else 'FAIL'}" + ("" if good else f"  {last[-1] if last else ''}"))
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    uf2 = sys.argv[1]
    names = [n.upper() for n in sys.argv[2:]] or list(BOARDS)
    sys.exit(0 if flash(uf2, names) else 1)
