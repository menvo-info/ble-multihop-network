# E3-auto-lan2

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T04:22:05.951 → 2026-11-13T04:32:06.445
- Ghi chú: E3: tắt B 5 s, 3 lần: kết nối lại, mất gói, retry | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 589 dòng; gói nhận theo đường: {'direct': 583, 'relayed': 1129}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 9.3 | 1 | 560 | 560 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.2 | 0.0 | -59.3 | thật |
| B | 1 | 8.4 | 4 | 500 | 500 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.9 | 0.0 | -39.8 | thật |
| C | 2 | 9.2 | 1 | 550 | 549 | 1 | 99.82% | 1 | 25 | 0 | 3 | 195.8 | 0.0 | -51.7 | thật |
| **Tổng** | | | | 1610 | 1609 | 1 | 99.94% | 1 | 25 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 576 | 80.7 | 80.0 | 104 | 153 |
| B | 563 | 131.2 | 131 | 153 | 207 |
| C | 558 | 196.6 | 190.0 | 248 | 490 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 04:22:07.755 | 04:22:28.381 | 20.63 |
| B | 04:22:07.980 | 04:22:35.931 | 27.95 |
| C | 04:22:07.879 | 04:22:44.231 | 36.35 |
| B | 04:24:40.583 | 04:24:46.535 | 5.95 |
| C | 04:24:40.983 | 04:24:46.933 | 5.95 |
| C | 04:27:10.034 | 04:27:16.586 | 6.55 |
| B | 04:27:10.534 | 04:27:16.637 | 6.1 |
| C | 04:29:39.986 | 04:29:46.535 | 6.55 |
| B | 04:29:40.635 | 04:29:46.553 | 5.92 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, NEW_SESSION: 3, ROOT_STATS: 171, ROOT_SUMMARY: 58, SCAN_START: 1, SENSORS: 1
