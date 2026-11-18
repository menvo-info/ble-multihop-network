"""Tóm tắt một lần chạy trong experiments/<run>/ (chỉ đọc, không sửa log gốc).

    python tools/summarize.py experiments/m1-pair-30min

PDR tính chỉ từ log Root:
  pdr_seq = số gói duy nhất / (seq lớn nhất - seq nhỏ nhất + 1), theo từng phiên (node, boot)
  pdr_gen = số gói duy nhất có g0 <= seq < g1 / (g1 - g0), với g0, g1 = "gen" (số gói đã tạo, do
            chính node báo) trong STATS_RX đầu và cuối của phiên -> tính được cả gói mất liền nhau
            mà pdr_seq không thấy, và không bị lệch khi bắt đầu ghi log muộn
"""
import collections
import json
import os
import statistics
import sys


def read_log(path):
    events, bad = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            host, _, raw = line.rstrip("\n").partition("\t")
            if not raw.startswith("{"):
                continue  # #PORT_OPEN, dòng rác lúc USB mở cổng
            try:
                e = json.loads(raw)
                if "t" not in e or "type" not in e:
                    raise ValueError
                e["_host"] = host
                events.append(e)
            except ValueError:
                bad += 1
    return events, bad


def summarize_root(events, bad):
    types = collections.Counter(e["type"] for e in events)
    print(f"  JSON lines: {len(events)}, malformed: {bad}")
    print("  events:", {k: types[k] for k in ("BOOT", "CONNECTED", "DISCONNECTED", "CHILD_READY", "DATA_RX",
                                              "STATS_RX", "ROUTE_CHANGE", "NEW_SESSION") if types[k]})
    sessions = collections.defaultdict(lambda: {"seqs": set(), "rx": 0, "checks": collections.Counter(),
                                                "gens": [], "retry": 0, "ack0": 0})
    for e in events:
        if e["type"] == "DATA_RX":
            s = sessions[(e["node"], e["boot"])]
            s["seqs"].add(e["seq"])
            s["rx"] += 1
            s["checks"][e["check"]] += 1
            s["retry"] += 1 if e["flags"] & 2 else 0
            s["ack0"] += 0 if e["ack"] else 1
        elif e["type"] == "STATS_RX":
            sessions[(e["node"], e["boot"])]["gens"].append(e["gen"])
    for (node, boot), s in sorted(sessions.items()):
        if not s["seqs"]:
            continue
        lo, hi = min(s["seqs"]), max(s["seqs"])
        uniq = len(s["seqs"])
        line = (f"  {node} boot={boot}: unique={uniq} seq={lo}..{hi} pdr_seq={100 * uniq / (hi - lo + 1):.2f}%"
                f" dup={s['checks']['DUP']} late={s['checks']['LATE']} gap={s['checks']['GAP']}"
                f" retry_rx={s['retry']} ack_not_sent={s['ack0']}")
        if len(s["gens"]) >= 2 and s["gens"][-1] > s["gens"][0]:
            g0, g1 = s["gens"][0], s["gens"][-1]
            got = sum(1 for q in s["seqs"] if g0 <= q < g1)
            line += f" | gen {g0}..{g1}: pdr_gen={100 * got / (g1 - g0):.2f}% ({got}/{g1 - g0})"
        print(line)
    disc = [e for e in events if e["type"] == "DISCONNECTED"]
    for e in disc:
        print(f"  DISCONNECTED {e.get('node')} reason={e.get('reason')} at t={e['t']} ({e['_host']})")


def summarize_node(events, bad):
    types = collections.Counter(e["type"] for e in events)
    rtts = [e["rtt_ms"] for e in events if e["type"] == "ACK_RX"]
    msg = f"  JSON lines: {len(events)}, malformed: {bad}; DATA_TX={types['DATA_TX']} ACK_RX={types['ACK_RX']}"
    msg += f" RETRY={types['RETRY']} DROP={types['DROP']} DISCONNECTED={types['DISCONNECTED']}"
    if rtts:
        rs = sorted(rtts)
        msg += (f"; RTT ms: mean={statistics.mean(rtts):.1f} median={statistics.median(rtts):.0f}"
                f" p95={rs[int(0.95 * (len(rs) - 1))]} max={rs[-1]}")
    print(msg)


def summarize(run_dir):
    for name in sorted(os.listdir(run_dir)):
        if not name.endswith(".log"):
            continue
        events, bad = read_log(os.path.join(run_dir, name))
        boots = [e for e in events if e["type"] == "BOOT"]
        fw = boots[-1].get("fw") if boots else "?"
        print(f"== {name} (fw {fw})")
        if name.startswith("R"):
            summarize_root(events, bad)
        else:
            summarize_node(events, bad)


if __name__ == "__main__":
    summarize(sys.argv[1])
