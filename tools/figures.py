"""figures.py — vẽ hình cho báo cáo (PNG để chèn Word + SVG), lưu ở docs/hinh/.

    python tools/figures.py

Hình vẽ từ thiết kế thật của firmware/gateway (không phải số liệu đo):
  kien-truc   : node -> Root -> USB -> gateway -> SQLite / MQTT -> analyze
  topology    : PAIR, CHAIN, STAR, DIAMOND (mũi tên = hướng dữ liệu lên Root)
  luong-goi   : DATA đi lên qua relay, ACK_ROOT đi ngược xuống; mất ACK -> gửi lại -> Root lọc trùng
  goi-tin     : bố cục byte của DATA, STATS, ACK_ROOT, HELLO (pico2w-wsn/src/wsn_proto.h)
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "hinh")

INK, INK2, LINE, SURFACE, FILL = "#0b0b0b", "#52514e", "#8a8984", "#ffffff", "#f1f0ec"
NODE = {"R": "#52514e", "A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
ACK = "#6250d6"

plt.rcParams.update({"font.size": 10, "text.color": INK, "figure.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE})


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"docs/hinh/{name}.png")


def box(ax, x, y, w, h, text, fc=FILL, ec=LINE, color=INK, size=10, bold=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", color=color, fontsize=size, fontweight="bold" if bold else None)


def arrow(ax, p, q, color=LINE, text=None, off=(0, 0.12), lw=1.4, style="-|>", ls="-", size=8.5, rad=0.0, shrink=2):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, color=color, lw=lw, linestyle=ls,
                                 shrinkA=shrink, shrinkB=shrink, connectionstyle=f"arc3,rad={rad}", zorder=3))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center", va="center",
                fontsize=size, color=INK2)


def node(ax, x, y, n, r=0.32, label=None):
    ax.add_patch(Circle((x, y), r, fc=NODE[n], ec=SURFACE, lw=2))
    ax.text(x, y, n, ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    if label:
        ax.text(x, y - r - 0.18, label, ha="center", va="top", fontsize=8, color=INK2)


# ------------------------------------------------------------------ 1. kiến trúc

def fig_architecture():
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    # mạng BLE
    ax.add_patch(FancyBboxPatch((0.15, 1.35), 5.5, 2.6, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="none", ec=LINE, lw=1, ls="--"))
    ax.text(0.3, 3.8, "Mạng cảm biến BLE (Pico 2 W, CYW43439)", fontsize=9, color=INK2, va="top")
    xs = {"C": 0.8, "B": 2.2, "A": 3.6, "R": 5.0}
    labels = {"C": "node lá\nPeripheral", "B": "relay\nPeripheral\n+ Central", "A": "relay\nPeripheral\n+ Central",
              "R": "Root\nCentral"}
    for n, x in xs.items():
        node(ax, x, 2.75, n, label=labels[n])
    for a, b in (("C", "B"), ("B", "A"), ("A", "R")):
        arrow(ax, (xs[a] + 0.34, 2.85), (xs[b] - 0.34, 2.85), color=INK, text="DATA, STATS", off=(0, 0.2), size=7.5)
        arrow(ax, (xs[b] - 0.34, 2.62), (xs[a] + 0.34, 2.62), color=ACK, text="ACK_ROOT", off=(0, -0.2), size=7.5)
    ax.text(2.9, 1.55, "Lên: GATT notify (characteristic DATA)   Xuống: write without response (ACK)",
            ha="center", fontsize=8, color=INK2)
    # gateway
    box(ax, 7.0, 2.75, 1.7, 0.8, "gateway.py\n(đọc JSON từ USB)", size=9)
    arrow(ax, (5.34, 2.75), (6.15, 2.75), color=INK)
    ax.text(5.75, 3.05, "USB\nJSON", ha="center", fontsize=7.5, color=INK2)
    box(ax, 9.3, 3.5, 1.9, 0.62, "SQLite wsn.db\nruns · data · stats · events", size=8)
    box(ax, 9.3, 2.45, 1.9, 0.62, "MQTT (Mosquitto)\nwsn/<node>/data …", size=8)
    box(ax, 9.3, 1.25, 1.9, 0.62, "analyze.py\nbảng chỉ số + biểu đồ", size=8)
    box(ax, 7.0, 1.25, 1.7, 0.62, "experiments/<run>/\nR.log (log gốc)", size=8)
    arrow(ax, (7.85, 2.95), (8.35, 3.4))
    arrow(ax, (7.85, 2.6), (8.35, 2.5))
    arrow(ax, (7.0, 2.35), (7.0, 1.56))
    ax.add_patch(FancyArrowPatch((10.25, 3.45), (10.25, 1.3), arrowstyle="-|>", mutation_scale=12, color=LINE,
                                 lw=1.2, connectionstyle="arc3,rad=-0.35"))
    ax.text(5.6, 0.35, "Mọi chỉ số tính được chỉ từ dữ liệu Root nhận (DATA + STATS), nên dùng được cả ngoài thực địa, "
                       "nơi không đọc được log USB của node.", ha="center", fontsize=8.5, color=INK2)
    save(fig, "kien-truc")


# ------------------------------------------------------------------ 2. topology

def fig_topology():
    fig, axs = plt.subplots(1, 4, figsize=(12, 3.4))
    specs = [
        ("PAIR (M1, E1)", {"R": (1, 0.3), "A": (1, 2.0)}, [("A", "R")], []),
        ("CHAIN CBA (E2–E5, E7)", {"R": (1, 0.0), "A": (1, 1.0), "B": (1, 2.0), "C": (1, 3.0)},
         [("C", "B"), ("B", "A"), ("A", "R")], []),
        ("STAR", {"R": (1, 0.3), "A": (0.1, 2.0), "B": (1, 2.0), "C": (1.9, 2.0)}, [("A", "R"), ("B", "R"), ("C", "R")], []),
        ("DIAMOND CAB (E6, E8)", {"R": (1, 0.0), "A": (0.3, 1.5), "B": (1.7, 1.5), "C": (1, 3.0)},
         [("A", "R"), ("B", "R"), ("C", "A")], [("C", "B")]),
    ]
    for ax, (title, pos, edges, backup) in zip(axs, specs):
        ax.set_xlim(-0.6, 2.6)
        ax.set_ylim(-0.6, 3.6)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontsize=10, fontweight="bold", loc="left")
        for a, b in edges:
            arrow(ax, pos[a], pos[b], color=INK, lw=1.6, shrink=17)
        for a, b in backup:
            arrow(ax, pos[a], pos[b], color=LINE, lw=1.4, ls="--", shrink=17)
        for n, (x, y) in pos.items():
            node(ax, x, y, n, r=0.27)
    axs[3].text(1, -0.55, "nét đứt = cha dự phòng", ha="center", fontsize=8, color=INK2)
    fig.text(0.5, -0.02, "Mũi tên: hướng dữ liệu đi lên Root. Topology chọn lúc build (WSN_TOPOLOGY, WSN_ORDER), "
                         "một file UF2 cho cả 4 board.", ha="center", fontsize=8.5, color=INK2)
    save(fig, "topology")


# ------------------------------------------------------------------ 3. luồng gói

def fig_flow():
    fig, ax = plt.subplots(figsize=(10, 6.4))
    xs = {"C": 1, "B": 3.4, "A": 5.8, "R": 8.2}
    ax.set_xlim(0, 9.4)
    ax.set_ylim(0.2, 11.0)
    ax.axis("off")
    for n, x in xs.items():
        node(ax, x, 10.6, n, r=0.3)
        ax.plot([x, x], [0.4, 10.25], color=LINE, lw=1, ls=":")
    ax.text(xs["C"] - 0.45, 10.6, "nguồn", fontsize=8, color=INK2, ha="right", va="center")
    ax.text(xs["R"] + 0.45, 10.6, "Root", fontsize=8, color=INK2, va="center")

    def msg(y, a, b, text, color=INK, ls="-", lost=False):
        x0, x1 = xs[a], xs[b]
        if lost:
            xm = (x0 + x1) / 2
            ax.plot([x0, xm], [y, y], color=color, lw=1.4, ls=ls)
            ax.text(xm, y, "✕", color="#e34948", ha="center", va="center", fontsize=13, fontweight="bold")
        else:
            arrow(ax, (x0, y), (x1, y), color=color, ls=ls, lw=1.4)
        ax.text((x0 + x1) / 2, y + 0.17, text, ha="center", fontsize=7.8, color=INK2)

    def note(x, y, text, ha="left"):
        ax.text(x, y, text, fontsize=7.8, color=INK, ha=ha, va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc=FILL, ec="none"))

    y = 9.4
    ax.text(0.1, y + 0.5, "① Gửi bình thường", fontsize=9, fontweight="bold")
    msg(y, "C", "B", "DATA seq=7 ttl=4 hop=0")
    msg(y - 0.55, "B", "A", "ttl=3 hop=1 (relay)")
    msg(y - 1.1, "A", "R", "ttl=2 hop=2")
    note(xs["R"] + 0.12, y - 1.55, "kiểm tra (C, boot, 7): OK\ngửi ACK về con đã đưa gói lên", ha="left")
    msg(y - 2.0, "R", "A", "ACK_ROOT C/7", color=ACK)
    msg(y - 2.45, "A", "B", "relay tra bảng source→con", color=ACK)
    msg(y - 2.9, "B", "C", "ACK_ROOT C/7", color=ACK)
    note(xs["C"] - 0.15, y - 3.3, "xóa seq 7 khỏi bảng chờ; RTT = thời điểm ACK − lúc gửi", ha="left")

    y = 5.0
    ax.text(0.1, y + 0.5, "② Mất ACK → gửi lại → Root lọc trùng", fontsize=9, fontweight="bold")
    msg(y, "C", "B", "DATA seq=8")
    msg(y - 0.45, "B", "A", "")
    msg(y - 0.9, "A", "R", "")
    note(xs["R"] + 0.12, y - 1.2, "seq 8: OK", ha="left")
    msg(y - 1.5, "R", "A", "ACK C/8", color=ACK)
    msg(y - 1.95, "A", "B", "ACK C/8 (mất)", color=ACK, lost=True)
    note(xs["C"] - 0.15, y - 2.4, "quá timeout (1 s × số hop) → gửi lại\ncùng (C, boot, 8) + cờ RETRY", ha="left")
    msg(y - 3.2, "C", "B", "DATA seq=8 RETRY")
    msg(y - 3.5, "B", "A", "")
    msg(y - 3.8, "A", "R", "")
    note(xs["R"] + 0.12, y - 4.1, "seq 8: DUP → không đếm lại,\nvẫn gửi ACK (ACK trước có thể đã mất)", ha="left")
    msg(y - 4.5, "R", "C", "ACK C/8 (qua A, B)", color=ACK)
    save(fig, "luong-goi")


# ------------------------------------------------------------------ 4. gói tin

def fig_packets():
    pk = [
        ("DATA (20 B)", [("hdr", 1), ("src", 1), ("ttl", 1), ("hop", 1), ("flags", 1), ("parent", 1), ("boot_id", 4),
                         ("seq", 4), ("ldr", 2), ("I×10", 2), ("vbat", 2)]),
        ("STATS (20 B)", [("hdr", 1), ("src", 1), ("rssi", 1), ("lost", 1), ("boot_id", 4), ("generated", 4),
                          ("retries", 2), ("qfull", 2), ("rtt_avg", 2), ("I_avg", 2)]),
        ("ACK_ROOT (12 B)", [("hdr", 1), ("src", 1), ("res", 2), ("boot_id", 4), ("seq", 4)]),
        ("HELLO (2 B)", [("hdr", 1), ("parent", 1)]),
    ]
    fill = {"hdr": "#d9d8d3", "boot_id": "#cfe0f6", "seq": "#cfe0f6", "src": "#cfe0f6"}
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.set_xlim(-3.2, 20.3)
    ax.set_ylim(-0.6, len(pk) * 1.0 + 0.3)
    ax.axis("off")
    for i, (name, fields) in enumerate(pk):
        y = (len(pk) - 1 - i) * 1.0 + 0.3
        ax.text(-0.3, y, name, ha="right", va="center", fontsize=9.5, fontweight="bold")
        x = 0
        for f, n in fields:
            ax.add_patch(plt.Rectangle((x, y - 0.3), n, 0.6, fc=fill.get(f, FILL), ec=SURFACE, lw=2))
            ax.text(x + n / 2, y, f, ha="center", va="center", fontsize=7.5 if n == 1 else 8.5)
            x += n
    for b in range(0, 21, 4):
        ax.text(b, -0.45, str(b), ha="center", fontsize=8, color=INK2)
    ax.text(10, -0.75, "byte", ha="center", fontsize=8, color=INK2)
    fig.text(0.5, -0.04, "hdr = (version << 4) | type. Danh tính gói = (source_id, boot_id, seq), tô xanh. "
                         "Mọi gói ≤ 20 byte, vừa một notification khi ATT MTU mặc định (23).",
             ha="center", fontsize=8.5, color=INK2)
    save(fig, "goi-tin")


if __name__ == "__main__":
    fig_architecture()
    fig_topology()
    fig_flow()
    fig_packets()
