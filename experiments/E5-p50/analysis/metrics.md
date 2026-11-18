# E5-p50

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T01:34:57.757 → 2026-11-13T01:40:58.048
- Ghi chú: E5: tăng tốc độ gửi: queue đầy, gói bỏ | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 350 dòng; gói nhận theo đường: {'direct': 1916, 'relayed': 3741}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 5.3 | 1 | 1895 | 1895 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.6 | 0.0 | -61.6 | thật |
| B | 1 | 5.0 | 2 | 1805 | 1805 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.4 | 0.0 | -50.9 | thật |
| C | 2 | 5.2 | 1 | 1874 | 1865 | 9 | 99.52% | 2 | 2 | 144 | 1 | 183.6 | 0.0 | -60.2 | thật |
| **Tổng** | | | | 5574 | 5565 | 9 | 99.84% | 2 | 2 | 144 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1912 | 78.9 | 79.0 | 101 | 198 |
| B | 1856 | 130.2 | 130.0 | 152 | 243 |
| C | 1862 | 181.8 | 180.0 | 204 | 339 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 01:34:59.499 | 01:35:20.204 | 20.7 |
| B | 01:34:59.649 | 01:35:27.753 | 28.1 |
| C | 01:34:59.550 | 01:35:36.252 | 36.7 |
| B | 01:40:29.204 | 01:40:34.550 | 5.35 |
| C | 01:40:29.199 | 01:40:34.649 | 5.45 |

## Số sự kiện Root

BOOT: 1, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, NEW_SESSION: 1, ROOT_STATS: 99, ROOT_SUMMARY: 34, SCAN_START: 1
