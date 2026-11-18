"""analyze.py — tính chỉ số của một lần chạy (run_id trong SQLite), xuất bảng + biểu đồ PNG.

    python gateway/analyze.py E2-chain                       # -> experiments/E2-chain/analysis/
    python gateway/analyze.py --compare E7-fast E7-lowpower  # bảng + biểu đồ so sánh nhiều run
    python gateway/analyze.py --all                          # phân tích lại mọi run trong DB

Mọi chỉ số chính chỉ dùng dữ liệu Root nhận (bảng data/stats/events) — đúng cả ngoài thực địa, nơi không có
log USB của node. Nếu experiments/<run>/ có log node (A.log...), thêm phân bố ACK RTT đo trên đồng hồ node.

Định nghĩa (mỗi phiên = một cặp (node, boot); node reset thì sang phiên mới):
  generated  = gen(STATS cuối) - gen(STATS đầu)   — số gói node tự báo đã tạo trong cửa sổ quan sát
  received   = số seq duy nhất Root nhận, với gen_đầu <= seq < gen_cuối
  PDR        = received / generated               (không tính dữ liệu cục bộ của Root)
  lost       = generated - received
  dup        = số gói Root nhận trùng (check=DUP), retry_rx = gói mang cờ RETRY
  retries, qfull, parent_lost = hiệu STATS cuối - đầu (bộ đếm cộng dồn của node)
  rtt_avg    = trung bình các rtt_avg_ms trong STATS (mỗi STATS = TB một chu kỳ, bỏ chu kỳ không có ACK)
  i_avg      = trung bình i_avg_x10/10 trong STATS (mA, chỉ node có INA219)
  outage     = khoảng trống giữa hai lần Root nhận gói mới của một node > 3 chu kỳ DATA
  reconnect  = Root: DISCONNECTED (con trực tiếp) -> CHILD_READY lại của cùng node
  route time = ROUTE_CHANGE: lần nhận cuối qua cha cũ -> lần nhận đầu qua cha mới (giờ máy tính)
"""
import argparse
import collections
import datetime as dt
import json
import os
import statistics
import sys

import wsn_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "gateway", "wsn.db")
NODES = ("A", "B", "C")
BATTERY_MAH = 2000.0  # pin 18650 của node; đổi bằng --battery-mah

# Màu theo node (cố định, không theo thứ hạng): 3 slot đầu của bảng màu tham chiếu, đạt kiểm tra CVD mọi cặp.
NODE_COLOR = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
RUN_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]  # --compare: tối đa 3 run trên một biểu đồ
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def ts(s):
    return dt.datetime.fromisoformat(s)


def pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def mean(v):
    return round(statistics.mean(v), 1) if v else None


def percentile(v, q):
    if not v:
        return None
    s = sorted(v)
    return s[int(q * (len(s) - 1))]


# ------------------------------------------------------------------ đọc DB

def load(db, run):
    r = db.execute("SELECT * FROM runs WHERE run_id = ?", (run,)).fetchone()
    if not r:
        sys.exit(f"run '{run}' không có trong DB — chạy gateway.py (hoặc gateway.py {run} --replay) trước")
    data = [dict(x) for x in db.execute("SELECT * FROM data WHERE run_id = ? ORDER BY host_ts", (run,))]
    stats = [dict(x) for x in db.execute("SELECT * FROM stats WHERE run_id = ? ORDER BY host_ts", (run,))]
    events = []
    for x in db.execute("SELECT host_ts, json FROM events WHERE run_id = ? ORDER BY host_ts", (run,)):
        e = json.loads(x["json"])
        e["_host"] = x["host_ts"]
        events.append(e)
    nlocal = db.execute("SELECT COUNT(*) FROM local_data WHERE run_id = ?", (run,)).fetchone()[0]
    return dict(r), data, stats, events, nlocal


def data_period_s(run):
    return 5.0 if (run.get("power") or "").upper() == "LOW_POWER" else 1.0


# ------------------------------------------------------------------ chỉ số

def sessions_metrics(data, stats):
    by = collections.defaultdict(lambda: {"data": [], "stats": []})
    for d in data:
        by[(d["node"], d["boot"])]["data"].append(d)
    for s in stats:
        by[(s["node"], s["boot"])]["stats"].append(s)
    out = []
    for (node, boot), g in sorted(by.items()):
        seqs = {d["seq"] for d in g["data"] if d["chk"] != "DUP"}
        st = g["stats"]
        m = {"node": node, "boot": boot, "rx_frames": len(g["data"]), "unique": len(seqs),
             "dup": sum(1 for d in g["data"] if d["chk"] == "DUP"),
             "late": sum(1 for d in g["data"] if d["chk"] == "LATE"),
             "retry_rx": sum(d["retry"] for d in g["data"]),
             "ack_test_drop": sum(1 for d in g["data"] if d["ack"] == -1),  # E4: Root cố ý bỏ ACK
             "stats_rx": len(st)}
        hops = collections.Counter(d["hop"] for d in g["data"])
        m["hop"] = hops.most_common(1)[0][0] if hops else None
        m["paths"] = dict(collections.Counter(d["path"] for d in g["data"]))
        m["parents"] = dict(collections.Counter(d["parent"] for d in g["data"]))
        m["fake"] = bool(g["data"]) and all(d["fake"] for d in g["data"])
        if len(st) >= 2 and st[-1]["gen"] > st[0]["gen"]:
            g0, g1 = st[0]["gen"], st[-1]["gen"]
            got = sum(1 for q in seqs if g0 <= q < g1)
            m.update(window=f"{g0}..{g1}", generated=g1 - g0, received=got, lost=(g1 - g0) - got,
                     pdr=pct(got, g1 - g0),
                     retries=st[-1]["retries"] - st[0]["retries"], qfull=st[-1]["qfull"] - st[0]["qfull"],
                     parent_lost=st[-1]["parent_lost"] - st[0]["parent_lost"],
                     duration_min=round((ts(st[-1]["host_ts"]) - ts(st[0]["host_ts"])).total_seconds() / 60, 1))
        if seqs:
            lo, hi = min(seqs), max(seqs)
            m["pdr_seq"] = pct(len(seqs), hi - lo + 1)
        rtts = [s["rtt_avg_ms"] for s in st if s["rtt_avg_ms"]]
        m["rtt_avg_ms"] = mean(rtts)
        cur = [s["i_avg_x10"] / 10 for s in st if s["i_avg_x10"] is not None and s["i_avg_x10"] != wsn_db.NO_CURRENT]
        m["i_avg_ma"] = mean(cur)
        rssi = [s["rssi"] for s in st if s["rssi"]]
        m["rssi_avg"] = mean(rssi)
        vb = [d["vbat_mv"] for d in g["data"] if d["vbat_mv"]]
        m["vbat_mv_avg"] = mean(vb)
        out.append(m)
    return out


def node_totals(sess, stats):
    """Gộp theo node mọi phiên có cửa sổ STATS (>= 2 STATS). Mẩu phiên ngắn lúc nạp lần lượt không có
    cửa sổ nên tự bị loại. Khoảng node tắt / đang khởi động lại không tạo gói nên không tính là mất."""
    out = []
    for n in NODES:
        ss = [m for m in sess if m["node"] == n and "generated" in m]
        if not ss:
            continue
        boots = {m["boot"] for m in ss}
        st = [s for s in stats if s["node"] == n and s["boot"] in boots]
        t = {"node": n, "sessions": len(ss), "boots": sorted(boots)}
        for k in ("generated", "received", "lost", "dup", "late", "retry_rx", "ack_test_drop", "retries", "qfull",
                  "parent_lost",
                  "duration_min"):
            t[k] = round(sum(m[k] for m in ss), 1) if k == "duration_min" else sum(m[k] for m in ss)
        t["pdr"] = pct(t["received"], t["generated"])
        hops = collections.Counter()
        for m in ss:
            hops[m["hop"]] += m["unique"]
        t["hop"] = hops.most_common(1)[0][0]
        t["fake"] = all(m["fake"] for m in ss)
        t["rtt_avg_ms"] = mean([s["rtt_avg_ms"] for s in st if s["rtt_avg_ms"]])
        t["i_avg_ma"] = mean([s["i_avg_x10"] / 10 for s in st
                              if s["i_avg_x10"] is not None and s["i_avg_x10"] != wsn_db.NO_CURRENT])
        t["rssi_avg"] = mean([s["rssi"] for s in st if s["rssi"]])
        vb = [m["vbat_mv_avg"] for m in ss if m["vbat_mv_avg"]]
        t["vbat_mv_avg"] = mean(vb)
        out.append(t)
    return out


def outages(data, period_s):
    """Khoảng Root không nhận gói mới của một node > 3 chu kỳ (mất kết nối, đổi tuyến, node tắt)."""
    out = []
    last = {}
    for d in data:
        if d["chk"] == "DUP":
            continue
        t = ts(d["host_ts"])
        key = d["node"]
        if key in last:
            gap = (t - last[key]).total_seconds()
            if gap > 3 * period_s:
                out.append({"node": key, "from": last[key].isoformat(timespec="milliseconds"),
                            "to": d["host_ts"], "gap_s": round(gap, 2)})
        last[key] = t
    return out


def reconnects(events):
    out, down = [], {}
    for e in events:
        if e["type"] == "DISCONNECTED" and e.get("link") == "child":
            down[e["node"]] = (e["_host"], e.get("reason"))
        elif e["type"] == "CHILD_READY" and e["node"] in down:
            t0, reason = down.pop(e["node"])
            out.append({"node": e["node"], "disconnected": t0, "ready": e["_host"], "reason": reason,
                        "s": round((ts(e["_host"]) - ts(t0)).total_seconds(), 2)})
    return out


def route_changes(events, data):
    out = []
    for e in events:
        if e["type"] != "ROUTE_CHANGE":
            continue
        node, old, new = e["node"], e["from"], e["to"]
        t_change = e["_host"]
        before = [d for d in data if d["node"] == node and d["parent"] == old and d["host_ts"] <= t_change]
        # Gói đầu tiên Root nhận sau đó mà không đi qua cha cũ (fw cũ có thể gửi vài gói parent="?" ngay sau
        # khi nối lại, trước khi nhận HELLO)
        after = [d for d in data if d["node"] == node and d["parent"] != old
                 and before and d["host_ts"] > before[-1]["host_ts"]]
        r = {"node": node, "from": old, "to": new, "at": t_change, "seq": e["seq"]}
        if before and after:
            r["last_old"] = before[-1]["host_ts"]
            r["first_new"] = after[0]["host_ts"]
            r["s"] = round((ts(after[0]["host_ts"]) - ts(before[-1]["host_ts"])).total_seconds(), 2)
        out.append(r)
    return out


def node_log_rtt(run):
    """Phân bố ACK RTT từ log USB của node (nếu có), theo boot của node."""
    out = {}
    d = os.path.join(ROOT, "experiments", run)
    for n in NODES:
        path = os.path.join(d, f"{n}.log")
        if not os.path.exists(path):
            continue
        by_boot = collections.defaultdict(list)
        boot = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                e = wsn_db.parse_line(line.partition("\t")[2])
                if not e:
                    continue
                if e["type"] == "BOOT":
                    boot = e.get("boot")
                elif e["type"] == "ACK_RX":
                    by_boot[boot].append(e["rtt_ms"])
        out[n] = dict(by_boot)
    return out


def analyze(db, run):
    r, data, stats, events, nlocal = load(db, run)
    period = data_period_s(r)
    sess = sessions_metrics(data, stats)
    mains = node_totals(sess, stats)
    rtt_logs = node_log_rtt(run)
    for m in mains:
        v = [x for b in m["boots"] for x in rtt_logs.get(m["node"], {}).get(b, [])]
        if v:
            m["node_rtt"] = {"n": len(v), "mean": mean(v), "median": statistics.median(v),
                             "p95": percentile(v, 0.95), "max": max(v)}
    res = {
        "run": r, "data_period_s": period, "local_data_rows": nlocal,
        "nodes": mains, "all_sessions": sess,
        "totals": {
            "generated": sum(m["generated"] for m in mains),
            "received": sum(m["received"] for m in mains),
            "lost": sum(m["lost"] for m in mains),
            "dup": sum(m["dup"] for m in mains),
            "retries": sum(m["retries"] for m in mains),
            "qfull": sum(m["qfull"] for m in mains),
            "ack_test_drop": sum(m["ack_test_drop"] for m in mains),
        },
        "reconnects": reconnects(events),
        "route_changes": route_changes(events, data),
        "outages": outages(data, period),
        "event_counts": dict(collections.Counter(e["type"] for e in events)),
    }
    t = res["totals"]
    t["pdr"] = pct(t["received"], t["generated"])
    by_path = collections.Counter(d["path"] for d in data if d["chk"] != "DUP")
    res["rx_by_path"] = dict(by_path)
    return res, data, stats, events


# ------------------------------------------------------------------ xuất bảng

def fmt(v, unit=""):
    return "–" if v is None else f"{v}{unit}"


def write_markdown(res, path):
    r = res["run"]
    L = [f"# {r['run_id']}", "",
         f"- Topology: {r.get('topology')}, chế độ: {r.get('power')}, fw: {r.get('fw')}, nguồn: {r.get('source')}",
         f"- Thời gian: {r.get('started_at')} → {r.get('ended_at')}",
         f"- Ghi chú: {r.get('note') or ''}",
         f"- Dữ liệu cục bộ Root (không tính PDR): {res['local_data_rows']} dòng; gói nhận theo đường: {res['rx_by_path']}",
         "", "## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)", "",
         "| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in res["nodes"]:
        L.append(f"| {m['node']} | {m['hop']} | {m['duration_min']} | {m['sessions']} | {m['generated']} | {m['received']} | {m['lost']} "
                 f"| {fmt(m['pdr'], '%')} | {m['dup']} | {m['retries']} | {m['qfull']} | {m['parent_lost']} "
                 f"| {fmt(m['rtt_avg_ms'])} | {fmt(m['i_avg_ma'])} | {fmt(m['rssi_avg'])} | {'giả' if m['fake'] else 'thật'} |")
    t = res["totals"]
    L.append(f"| **Tổng** | | | | {t['generated']} | {t['received']} | {t['lost']} | {fmt(t['pdr'], '%')} | {t['dup']} "
             f"| {t['retries']} | {t['qfull']} | | | | | |")
    if t["ack_test_drop"]:
        L += ["", f"Test E4: Root cố ý bỏ {t['ack_test_drop']} ACK; Root nhận {t['dup']} gói trùng (đã lọc, không tính "
                  f"vào số gói nhận); node gửi lại {t['retries']} lần."]
    cur = [m for m in res["nodes"] if m["i_avg_ma"] and m["i_avg_ma"] > 0.5]
    if cur:
        L += ["", f"## Ước tính tuổi thọ pin ({BATTERY_MAH} mAh, dòng TB đo bằng INA219 phía pin)", "",
              "| Node | Dòng TB (mA) | Ước tính (giờ) | (ngày) |", "|---|---|---|---|"]
        for m in cur:
            h = BATTERY_MAH / m["i_avg_ma"]
            L.append(f"| {m['node']} | {m['i_avg_ma']} | {h:.0f} | {h / 24:.1f} |")
        L.append("")
        L.append("Ước tính thô = dung lượng / dòng TB; bỏ qua sụt dung lượng theo nhiệt độ, điện áp cắt và xung dòng "
                 "ngắn INA219 không bắt được.")
    if any("node_rtt" in m for m in res["nodes"]):
        L += ["", "## ACK RTT đo trên node (log USB)", "", "| Node | n | TB | Trung vị | p95 | Max |", "|---|---|---|---|---|---|"]
        for m in res["nodes"]:
            x = m.get("node_rtt")
            if x:
                L.append(f"| {m['node']} | {x['n']} | {x['mean']} | {x['median']} | {x['p95']} | {x['max']} |")
    if res["reconnects"]:
        L += ["", "## Kết nối lại (Root thấy con trực tiếp)", "", "| Node | Mất lúc | Sẵn sàng lại | Thời gian (s) | Lý do |",
              "|---|---|---|---|---|"]
        for x in res["reconnects"]:
            L.append(f"| {x['node']} | {x['disconnected'][11:]} | {x['ready'][11:]} | {x['s']} | {x['reason']} |")
    if res["route_changes"]:
        L += ["", "## Đổi tuyến", "", "| Node | Từ | Sang | Nhận cuối qua cha cũ | Nhận đầu qua cha mới | Thời gian (s) |",
              "|---|---|---|---|---|---|"]
        for x in res["route_changes"]:
            L.append(f"| {x['node']} | {x['from']} | {x['to']} | {x.get('last_old', '–')[11:]} | {x.get('first_new', '–')[11:]} "
                     f"| {fmt(x.get('s'))} |")
    if res["outages"]:
        L += ["", f"## Khoảng gián đoạn (> 3 × {res['data_period_s']} s không nhận gói mới)", "",
              "| Node | Từ | Tới | Dài (s) |", "|---|---|---|---|"]
        for x in res["outages"]:
            L.append(f"| {x['node']} | {x['from'][11:]} | {x['to'][11:]} | {x['gap_s']} |")
    L += ["", "## Số sự kiện Root", "", ", ".join(f"{k}: {v}" for k, v in sorted(res["event_counts"].items())), ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------ biểu đồ

def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
    })
    return plt


def chart_timeline(res, data, events, path):
    """Mỗi gói mới Root nhận = một vạch ở hàng của node; khoảng trống = gián đoạn. Đánh dấu đổi tuyến."""
    plt = plt_setup()
    if not data:
        return
    t0 = ts(data[0]["host_ts"])
    nodes = [n for n in NODES if any(d["node"] == n for d in data)]
    fig, ax = plt.subplots(figsize=(9, 0.7 * len(nodes) + 1.6))
    for i, n in enumerate(nodes):
        xs = [(ts(d["host_ts"]) - t0).total_seconds() / 60 for d in data if d["node"] == n and d["chk"] != "DUP"]
        ax.vlines(xs, i - 0.32, i + 0.32, color=NODE_COLOR[n], linewidth=0.6)
    for x in res["route_changes"]:
        m = (ts(x["at"]) - t0).total_seconds() / 60
        i = nodes.index(x["node"]) if x["node"] in nodes else 0
        ax.annotate(f"{x['from']}→{x['to']}", (m, i + 0.36), fontsize=8, color=INK2, ha="center", va="bottom")
    ax.set_yticks(range(len(nodes)), [f"Node {n}" for n in nodes])
    ax.set_ylim(-0.6, len(nodes) - 0.2)
    ax.set_xlabel("Thời gian từ lúc bắt đầu (phút)")
    ax.set_ylabel("Node gửi")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"{res['run']['run_id']}: gói Root nhận theo thời gian (mỗi vạch = 1 gói)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_series(res, stats, key, scale, ylabel, title, path, skip=lambda v: False):
    plt = plt_setup()
    mains = {(m["node"], b) for m in res["nodes"] for b in m["boots"]}
    rows = [s for s in stats if (s["node"], s["boot"]) in mains and s[key] is not None and not skip(s[key])]
    if not rows:
        return False
    t0 = ts(stats[0]["host_ts"])
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for n in NODES:
        pts = [((ts(s["host_ts"]) - t0).total_seconds() / 60, s[key] * scale) for s in rows if s["node"] == n]
        if not pts:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=NODE_COLOR[n], linewidth=2, label=f"Node {n}")
        ax.annotate(f"{n}", pts[-1], xytext=(4, 0), textcoords="offset points", color=INK2, va="center", fontsize=9)
    ax.set_xlabel("phút từ lúc bắt đầu")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def chart_rtt(res, run, path):
    """Phân bố RTT trên node (nếu có log node), nếu không thì cột RTT TB từ STATS."""
    plt = plt_setup()
    logs = node_log_rtt(run)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    nodes = res["nodes"]
    if any("node_rtt" in m for m in nodes):
        groups = [(m, [x for b in m["boots"] for x in logs[m["node"]].get(b, [])]) for m in nodes if "node_rtt" in m]
        bp = ax.boxplot([g[1] for g in groups], widths=0.45, showfliers=False, patch_artist=True,
                        medianprops={"color": INK, "linewidth": 2})
        for patch, (m, _) in zip(bp["boxes"], groups):
            patch.set_facecolor(NODE_COLOR[m["node"]])
            patch.set_edgecolor(SURFACE)
        ax.set_xticks(range(1, len(groups) + 1), [f"{m['node']}\n{m['hop'] + 1} hop" for m, _ in groups])
        ax.set_title(f"{res['run']['run_id']}: ACK RTT trên node (ms)")
    else:
        ms = [m for m in nodes if m["rtt_avg_ms"]]
        if not ms:
            plt.close(fig)
            return False
        ax.bar(range(len(ms)), [m["rtt_avg_ms"] for m in ms], width=0.5, color=[NODE_COLOR[m["node"]] for m in ms])
        for i, m in enumerate(ms):
            ax.annotate(f"{m['rtt_avg_ms']}", (i, m["rtt_avg_ms"]), xytext=(0, 3), textcoords="offset points",
                        ha="center", color=INK2, fontsize=9)
        ax.set_xticks(range(len(ms)), [f"{m['node']}\n{m['hop'] + 1} hop" for m in ms])
        ax.set_title(f"{res['run']['run_id']}: ACK RTT TB từ STATS (ms)")
    ax.set_ylabel("ACK RTT (ms)")
    ax.set_xlabel("Node (số chặng tới Root)")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def run_analysis(db, run):
    res, data, stats, events = analyze(db, run)
    out = os.path.join(ROOT, "experiments", run, "analysis")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    write_markdown(res, os.path.join(out, "metrics.md"))
    chart_timeline(res, data, events, os.path.join(out, "timeline.png"))
    chart_rtt(res, run, os.path.join(out, "rtt.png"))
    chart_series(res, stats, "i_avg_x10", 0.1, "mA", f"{run}: dòng trung bình mỗi chu kỳ STATS (INA219)",
                 os.path.join(out, "current.png"), skip=lambda v: v == wsn_db.NO_CURRENT)
    chart_series(res, stats, "rssi", 1, "dBm", f"{run}: RSSI tới node cha", os.path.join(out, "rssi.png"),
                 skip=lambda v: v == 0)
    t = res["totals"]
    print(f"{run}: PDR {fmt(t['pdr'], '%')} ({t['received']}/{t['generated']}), lost {t['lost']}, dup {t['dup']}, "
          f"retries {t['retries']}, route changes {len(res['route_changes'])} -> {os.path.relpath(out, ROOT)}")
    for m in res["nodes"]:
        print(f"  {m['node']} hop {m['hop']}: PDR {fmt(m['pdr'], '%')} rtt {fmt(m['rtt_avg_ms'])} ms "
              f"i {fmt(m['i_avg_ma'])} mA rssi {fmt(m['rssi_avg'])}")
    return res


def compare(db, runs, out_name):
    """Bảng + biểu đồ so sánh nhiều run (E2 theo số hop, E7 FAST vs LOW_POWER)."""
    results = [analyze(db, r)[0] for r in runs]
    out = os.path.join(ROOT, "experiments", out_name)
    os.makedirs(out, exist_ok=True)
    L = [f"# So sánh: {', '.join(runs)}", "",
         "| Run | Chế độ | Node | Hop | Phút | PDR | Mất | Retry | RTT TB (ms) | RTT p95 node (ms) | Dòng TB (mA) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for res in results:
        for m in res["nodes"]:
            p95 = m.get("node_rtt", {}).get("p95")
            L.append(f"| {res['run']['run_id']} | {res['run'].get('power')} | {m['node']} | {m['hop']} | {m['duration_min']} "
                     f"| {fmt(m['pdr'], '%')} | {m['lost']} | {m['retries']} | {fmt(m['rtt_avg_ms'])} | {fmt(p95)} "
                     f"| {fmt(m['i_avg_ma'])} |")
    with open(os.path.join(out, "compare.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(out, "compare.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    plt = plt_setup()
    for key, ylabel, fname in (("rtt_avg_ms", "ms", "compare_rtt.png"), ("i_avg_ma", "mA", "compare_current.png"),
                               ("pdr", "%", "compare_pdr.png")):
        if not any(m[key] is not None for res in results for m in res["nodes"]):
            continue
        fig, ax = plt.subplots(figsize=(7, 3.6))
        k = len(results)
        w = 0.8 / k
        for j, res in enumerate(results[:3]):
            xs, ys = [], []
            for i, n in enumerate(NODES):
                m = next((m for m in res["nodes"] if m["node"] == n), None)
                if m and m[key] is not None:
                    xs.append(i + (j - (k - 1) / 2) * w)
                    ys.append(m[key])
            ax.bar(xs, ys, width=w - 0.03, color=RUN_COLORS[j], label=res["run"]["run_id"])
            for x, y in zip(xs, ys):
                ax.annotate(f"{y:g}", (x, y), xytext=(0, 3), textcoords="offset points", ha="center",
                            color=INK2, fontsize=8)
        ax.set_xticks(range(len(NODES)), [f"Node {n}" for n in NODES])
        ax.set_ylabel(ylabel)
        ax.grid(axis="x", visible=False)
        ax.set_title({"rtt_avg_ms": "ACK RTT trung bình", "i_avg_ma": "Dòng trung bình (INA219)",
                      "pdr": "PDR"}[key])
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3)
        fig.tight_layout()
        fig.savefig(os.path.join(out, fname), dpi=150)
        plt.close(fig)
    print(f"compare -> {os.path.relpath(out, ROOT)}")


def main():
    global BATTERY_MAH
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--out", help="--compare: thư mục kết quả trong experiments/ (mặc định compare-<run1>-<run2>)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--battery-mah", type=float, default=BATTERY_MAH, help="dung lượng pin để ước tính tuổi thọ")
    a = ap.parse_args()
    BATTERY_MAH = a.battery_mah
    db = wsn_db.connect(a.db)
    runs = a.runs
    if a.all:
        runs = [r["run_id"] for r in db.execute("SELECT run_id FROM runs ORDER BY started_at")]
    if not runs:
        sys.exit(__doc__)
    if a.compare:
        compare(db, runs, a.out or "compare-" + "-".join(runs))
    else:
        for r in runs:
            run_analysis(db, r)


if __name__ == "__main__":
    main()
