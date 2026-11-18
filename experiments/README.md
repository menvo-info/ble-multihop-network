# Experiment results

Each folder is one run produced by `tools/exp.py`. Only the analysis output is published here: `metrics.md` (summary table), `metrics.json` (all numbers) and the figures. Raw serial logs and dashboard videos are kept locally to keep the repository small.

Setup for every run: four Pico 2 W boards on one desk, FAST power profile (50 ms connection interval), one DATA packet per node per second, boards on USB power except E7. PDR is packets received by the Root divided by packets the node reports as generated (from its STATS packets). RTT is measured by the node, from sending a packet to receiving the Root's ACK.

| Run | Topology | Scenario | Duration | PDR | Notes |
|---|---|---|---|---|---|
| [E1](E1/analysis/metrics.md) | PAIR | Single hop | 30 min | 100% (1,820) | RTT 79 ms |
| [E1-mesh-2h](E1-mesh-2h/analysis/metrics.md) | MESH | Long run | 58 min | 100% (10,460) | Stopped early by an OS restart |
| [E1-mesh-2h-lan2](E1-mesh-2h-lan2/analysis/metrics.md) | MESH | Long run | 2 h | 100% (21,470) | 0 retries, 0 reroutes |
| [E2](E2/analysis/metrics.md), [E2-lan2](E2-lan2/analysis/metrics.md) | CHAIN C→B→A→R | 1–3 hops | 30 min each | 100% | RTT 80 / 130 / 181 ms |
| [E2-star](E2-star/analysis/metrics.md), [E2-mesh](E2-mesh/analysis/metrics.md) | STAR, MESH | All direct | 30 min each | 100% | RTT about 80 ms |
| [E3-auto](E3-auto/analysis/metrics.md), [E3-auto-lan2](E3-auto-lan2/analysis/metrics.md) | CHAIN | Relay B reset 3 times | 9 min each | 99.88% / 99.94% | 2 / 1 packets lost, 25 retries |
| [E4-ack10](E4-ack10/analysis/metrics.md), [ack30](E4-ack30/analysis/metrics.md), [ack50](E4-ack50/analysis/metrics.md) | CHAIN | Root drops 10/30/50% of ACKs | 7 min each | 100% | 78 / 348 / 678 retries, all duplicates filtered |
| [E5-p200](E5-p200/analysis/metrics.md), [p100](E5-p100/analysis/metrics.md), [p50](E5-p50/analysis/metrics.md) | CHAIN | Data period 200/100/50 ms | 5 min each | 100 / 100 / 99.84% | Relay queue full 144 times at 50 ms |
| [E6](E6/analysis/metrics.md), [E6-lan2](E6-lan2/analysis/metrics.md) | DIAMOND | Parent of C reset 6 times | 9 min each | 99.87% / 100% | Reroute about 5.7 s (4 s supervision timeout) |
| [E6-u](E6-u/analysis/metrics.md), [E6-u-lan2](E6-u-lan2/analysis/metrics.md) | DIAMOND | Parent of C loses its uplink | 9 min each | 99.76% / 99.94% | Reroute median 1.9 s |
| [E7-FAST](E7-FAST/analysis/metrics.md) | CHAIN | Battery powered | 21 min | 100% (3,750) | 33.9 mA (B), 35.9 mA (C) |
| [E9](E9/analysis/metrics.md), [E9-lan2](E9-lan2/analysis/metrics.md), [E9-lan3](E9-lan3/analysis/metrics.md) | MESH | Root ignores A, then A+B, then B+C | 12 min each | 100% (6,590) | 23 reroutes, median 4.05 s, no loops |

Totals over all 23 runs: 93,844 packets generated, 93,825 received (99.98%), about 8 hours of traffic.

## Deep-sleep prototype

`SLEEP-B-*`: the `tools/sleepnode` firmware on one board, 10 s period, received by the laptop's Bluetooth adapter.

| Mode | Cycles completed by the board | Packets seen by the laptop | Awake time per cycle |
|---|---|---|---|
| [PSTATE](SLEEP-B-PSTATE/summary.md) | 100 / 100 | 100% | 1,252 ms |
| [DORMANT](SLEEP-B-DORMANT/summary.md) | 100 / 100 | 95% | 1,251 ms |
| [AWAKE](SLEEP-B-AWAKE/summary.md) (baseline) | 30 / 30 | 90% | 1,252 ms |

The board completed every cycle in all three modes. Missing packets are on the receiving side: the Windows Bluetooth stack scans sparsely and caught about two copies of each advertisement on average.

## Timing analysis

[QUY_LUAT/quy_luat.md](QUY_LUAT/quy_luat.md) (Vietnamese) breaks every node start-up into phases (radio boot, advertising, connection, service discovery, first ACK), reports reroute times per topology, and builds the link-quality table used for the shortest-path computation.
