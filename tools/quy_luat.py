"""quy_luat.py — rút "quy luật" thời gian của mạng từ các lượt thực nghiệm (đầu vào cho lịch ngủ/thức và chọn đường).

    python tools/quy_luat.py                       # mọi run E* có log node, ghi experiments/QUY_LUAT/
    python tools/quy_luat.py E9 E9-lan2 ...

Đọc log USB của node (A/B/C.log, mỗi dòng "<giờ máy>\\t<json>") + metrics.json do analyze.py tạo + gateway/wsn.db.
Tính:
  1. Khởi động → tham gia mạng: BOOT → ADV_START → CONNECTED → PARENT → ACK đầu tiên (đo trên đồng hồ node).
  2. Mất cha → có cha mới (node tự đo: DISCONNECTED → PARENT kế tiếp).
  3. ACK RTT theo độ sâu (depth = số hop tới Root, lấy từ sự kiện PARENT gần nhất).
  4. Root thấy con kết nối lại / đổi tuyến (metrics.json), theo topology và lý do.
  5. Chất lượng từng liên kết con → cha: RSSI, RTT, tỉ lệ gói phải gửi lại (từ DB).
"""
import collections
import glob
import json
import os
import sqlite3
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
OUT = os.path.join(EXP, "QUY_LUAT")


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def summ(xs, unit=""):
    if not xs:
        return "–", "–", "–", "–", 0
    return (f"{st.mean(xs):.2f}{unit}", f"{st.median(xs):.2f}{unit}", f"{pct(xs, 0.95):.2f}{unit}", f"{max(xs):.2f}{unit}",
            len(xs))


def load_node(path):
    ev = []
    for line in open(path, encoding="utf-8", errors="replace"):
        _, _, rest = line.rstrip("\n").partition("\t")
        if rest.startswith("{"):
            try:
                ev.append(json.loads(rest))
            except ValueError:
                pass
    return ev


def link_cost(rssi, retry_rate):
    """Chi phí 1 liên kết: 1 (mỗi hop) + phạt RSSI yếu hơn -70 dBm (1 / 10 dB) + phạt gửi lại (10 x tỉ lệ)."""
    return 1 + max(0.0, (-rssi - 70) / 10) + 10 * retry_rate


def dijkstra_section(link):
    """Root tính đường ngắn nhất cho mọi node từ bảng liên kết đo được (minh họa)."""
    import heapq
    edges = collections.defaultdict(list)          # cha -> [(con, chi phí)]
    rows = []
    for (node, par), v in sorted(link.items()):
        if not v["rssi"]:
            continue
        c = link_cost(st.mean(v["rssi"]), v["retries"] / max(v["gen"], 1))
        edges[par].append((node, c))
        rows.append(f"| {node} → {par} | {st.mean(v['rssi']):.1f} | {100 * v['retries'] / max(v['gen'], 1):.2f}% | {c:.2f} |")
    out = ["", "## 7. Đường ngắn nhất do Root tính (Dijkstra trên chi phí liên kết đo được)", "",
           "Chi phí = 1 mỗi hop + (RSSI yếu hơn −70 dBm: 1 điểm / 10 dB) + 10 × tỉ lệ gửi lại.", "",
           "| Liên kết | RSSI TB | Gửi lại | Chi phí |", "|---|---|---|---|"] + rows
    def solve(banned=()):
        dist, prev, pq = {"R": 0.0}, {}, [(0.0, "R")]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e9):
                continue
            for v, c in edges.get(u, []):
                if (v, u) in banned:
                    continue
                if d + c < dist.get(v, 1e9):
                    dist[v], prev[v] = d + c, u
                    heapq.heappush(pq, (d + c, v))
        return dist, prev
    def path(prev, n):
        p = [n]
        while p[-1] in prev:
            p.append(prev[p[-1]])
        return " → ".join(p)
    for title, banned in [("Mọi liên kết dùng được", ()),
                          ("Giả lập A mất liên kết thẳng tới Root (như lệnh deny A)", (("A", "R"),)),
                          ("Giả lập A và B mất liên kết thẳng tới Root (deny AB)", (("A", "R"), ("B", "R")))]:
        dist, prev = solve(banned)
        out += ["", f"**{title}**", "", "| Node | Đường | Tổng chi phí |", "|---|---|---|"]
        for n in "ABC":
            out.append(f"| {n} | {path(prev, n) if n in dist else 'không có đường'} | "
                       f"{dist[n]:.2f} |" if n in dist else f"| {n} | không có đường | – |")
    return out


def main():
    runs = sys.argv[1:] or sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(EXP, "E*", "A.log")))
    meta = {}
    for r in runs:
        mj = os.path.join(EXP, r, "analysis", "metrics.json")
        if os.path.exists(mj):
            meta[r] = json.load(open(mj, encoding="utf-8"))
    join = collections.defaultdict(list)       # giai đoạn -> [s]
    rejoin = collections.defaultdict(list)     # topology -> [s]  (node tự đo)
    rtt = collections.defaultdict(list)        # depth -> [ms]
    tries = collections.Counter()
    for r in runs:
        topo = meta.get(r, {}).get("run", {}).get("topology", "?").split()[0]
        for n in "ABC":
            p = os.path.join(EXP, r, f"{n}.log")
            if not os.path.exists(p):
                continue
            ev = load_node(p)
            depth = None
            boot_t = None
            seen = {}
            lost_t = None
            for e in ev:
                ty, t = e.get("type"), e.get("t")
                if t is None:
                    continue
                if ty == "BOOT" and e.get("state") == "START":
                    boot_t, seen, depth, lost_t = t, {}, None, None
                    continue
                if boot_t is not None and ty in ("ADV_START", "CONNECTED", "PARENT", "ACK_RX") and ty not in seen:
                    seen[ty] = t
                    if ty == "ACK_RX" and len(seen) == 4:
                        join["BOOT → bắt đầu quảng bá"].append((seen["ADV_START"] - boot_t) / 1000)
                        join["quảng bá → được cha kết nối"].append((seen["CONNECTED"] - seen["ADV_START"]) / 1000)
                        join["kết nối → nhận HELLO (có cha, biết đường)"].append((seen["PARENT"] - seen["CONNECTED"]) / 1000)
                        join["có cha → ACK đầu tiên từ Root"].append((seen["ACK_RX"] - seen["PARENT"]) / 1000)
                        join["TỔNG: BOOT → ACK đầu tiên"].append((seen["ACK_RX"] - boot_t) / 1000)
                if ty == "PARENT":
                    depth = e.get("depth")
                    if lost_t is not None:
                        rejoin[topo].append((t - lost_t) / 1000)
                        lost_t = None
                elif ty == "DISCONNECTED" and e.get("link") == "parent" and lost_t is None:
                    lost_t = t
                elif ty == "ACK_RX" and depth:
                    rtt[depth].append(e.get("rtt_ms", 0))
                    tries[e.get("tries", 1)] += 1
    rc = collections.defaultdict(list)
    rt = collections.defaultdict(list)
    for r, m in meta.items():
        topo = m["run"].get("topology", "?").split()[0]
        for x in m.get("reconnects", []):
            rc[(topo, x.get("reason"))].append(x["s"])
        for x in m.get("route_changes", []):
            rt[topo].append(x["s"])

    # 5. liên kết con -> cha (DB): RSSI trong STATS + RTT; cha lấy từ gói DATA gần nhất trước STATS
    db = sqlite3.connect(f"file:{os.path.join(ROOT, 'gateway', 'wsn.db')}?mode=ro", uri=True)
    q = ",".join("?" * len(runs))
    link = collections.defaultdict(lambda: {"rssi": [], "rtt": [], "gen": 0, "retries": 0, "runs": set()})
    for run in runs:
        last_parent = {}
        rows = db.execute("SELECT 'd', t_ms, node, boot, parent, NULL, NULL, NULL, NULL FROM data WHERE run_id=? "
                          "UNION ALL SELECT 's', t_ms, node, boot, NULL, rssi, rtt_avg_ms, gen, retries FROM stats "
                          "WHERE run_id=? ORDER BY 2", (run, run)).fetchall()
        prev = {}
        for kind, t, node, boot, parent, rssi, rtt_ms, gen, retries in rows:
            if kind == "d":
                last_parent[(node, boot)] = parent
                continue
            par = last_parent.get((node, boot))
            if not par:
                continue
            L = link[(node, par)]
            L["runs"].add(run)
            if rssi:
                L["rssi"].append(rssi)
            if rtt_ms:
                L["rtt"].append(rtt_ms)
            k = (node, boot)
            if k in prev and gen is not None and prev[k][0] is not None and gen >= prev[k][0]:
                L["gen"] += gen - prev[k][0]
                L["retries"] += max(0, (retries or 0) - (prev[k][1] or 0))
            prev[k] = (gen, retries)
    db.close()

    os.makedirs(OUT, exist_ok=True)
    L = [f"# Quy luật thời gian của mạng (từ {len(runs)} lượt thực nghiệm)", "",
         "Lượt: " + ", ".join(runs), "",
         "## 1. Khởi động → tham gia mạng (đồng hồ node, mỗi lần node khởi động / reset)", "",
         "| Giai đoạn | TB (s) | Trung vị | p95 | Max | n |", "|---|---|---|---|---|---|"]
    for k, v in join.items():
        L.append(f"| {k} | " + " | ".join(map(str, summ(v))) + " |")
    L += ["", "## 2. Node mất cha → có cha mới (node tự đo DISCONNECTED → PARENT)", "",
          "| Topology | TB (s) | Trung vị | p95 | Max | n |", "|---|---|---|---|---|---|"]
    for k, v in sorted(rejoin.items()):
        L.append(f"| {k} | " + " | ".join(map(str, summ(v))) + " |")
    L += ["", "## 3. ACK RTT theo số hop (node → Root → ACK về node)", "",
          "| Hop (depth) | TB (ms) | Trung vị | p95 | Max | n |", "|---|---|---|---|---|---|"]
    for d in sorted(rtt):
        L.append(f"| {d} | " + " | ".join(map(str, summ(rtt[d]))) + " |")
    if len(rtt) >= 2:
        ds = sorted(rtt)
        inc = [(st.median(rtt[b]) - st.median(rtt[a])) / (b - a) for a, b in zip(ds, ds[1:])]
        L.append(f"\nMỗi hop thêm (trung vị): {', '.join(f'{x:.0f} ms' for x in inc)}. "
                 f"ACK nhận ở lần gửi đầu: {100 * tries[1] / max(sum(tries.values()), 1):.2f}%.")
    L += ["", "## 4. Root thấy con kết nối lại (mất → sẵn sàng), theo topology và lý do ngắt", "",
          "Lý do 0x08 = hết supervision timeout (con/cha mất hẳn), 0x16 = phía Root chủ động ngắt (lệnh deny), 0x13 = phía kia ngắt.", "",
          "| Topology | Lý do | TB (s) | Trung vị | p95 | Max | n |", "|---|---|---|---|---|---|---|"]
    for (topo, why), v in sorted(rc.items()):
        L.append(f"| {topo} | {why} | " + " | ".join(map(str, summ(v))) + " |")
    L += ["", "## 5. Đổi tuyến (gói cuối qua cha cũ → gói đầu qua cha mới, phía Root)", "",
          "| Topology | TB (s) | Trung vị | p95 | Max | n |", "|---|---|---|---|---|---|"]
    for k, v in sorted(rt.items()):
        L.append(f"| {k} | " + " | ".join(map(str, summ(v))) + " |")
    L += ["", "## 6. Chất lượng liên kết con → cha (đầu vào chi phí cho thuật toán đường ngắn nhất)", "",
          "RTT là RTT đầu-cuối của node khi đi qua cha đó (gồm cả các hop phía trên). Tỉ lệ gửi lại = retries / gói tạo.", "",
          "| Liên kết | Số lượt | RSSI TB (dBm) | RSSI độ lệch | RTT TB (ms) | Gói tạo | Gửi lại | Tỉ lệ gửi lại |",
          "|---|---|---|---|---|---|---|---|"]
    for (node, par), v in sorted(link.items()):
        if not v["rssi"] and not v["gen"]:
            continue
        sd = st.pstdev(v["rssi"]) if len(v["rssi"]) > 1 else 0
        L.append(f"| {node} → {par} | {len(v['runs'])} | {st.mean(v['rssi']):.1f} | {sd:.1f} | "
                 f"{(st.mean(v['rtt']) if v['rtt'] else 0):.0f} | {v['gen']} | {v['retries']} | "
                 f"{100 * v['retries'] / max(v['gen'], 1):.2f}% |")
    L += dijkstra_section(link)
    md = "\n".join(L) + "\n"
    open(os.path.join(OUT, "quy_luat.md"), "w", encoding="utf-8").write(md)
    json.dump({"join": join, "rejoin": rejoin, "rtt": {str(k): v for k, v in rtt.items()},
               "reconnect": {f"{a}|{b}": v for (a, b), v in rc.items()}, "route_change": rt},
              open(os.path.join(OUT, "quy_luat.json"), "w", encoding="utf-8"))
    print(md)


if __name__ == "__main__":
    sys.exit(main())
