# E2

- Topology: CHAIN CBA, chế độ: FAST, fw: 9e034a2, nguồn: serial
- Thời gian: 2026-11-12T23:48:07.386 → 2026-11-13T00:19:07.814
- Ghi chú: E2: 1-3 hop, 30 phút: PDR, RTT theo số hop | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 1849 dòng; gói nhận theo đường: {'direct': 1841, 'relayed': 3654}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.5 | 0.0 | -68.5 | thật |
| B | 1 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.3 | 0.0 | -51.4 | thật |
| C | 2 | 30.2 | 1 | 1810 | 1810 | 0 | 100.0% | 0 | 0 | 0 | 0 | 182.2 | 0.0 | -60.8 | thật |
| **Tổng** | | | | 5450 | 5450 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1836 | 80.9 | 81.0 | 103 | 163 |
| B | 1829 | 130.7 | 130 | 153 | 234 |
| C | 1820 | 182.6 | 181.0 | 207 | 304 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 23:48:09.222 | 23:48:29.757 | 20.54 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, ROOT_STATS: 549, ROOT_SUMMARY: 184, SCAN_START: 1, SENSORS: 1
