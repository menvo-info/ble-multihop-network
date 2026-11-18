# E3-auto

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T00:56:22.120 → 2026-11-13T01:06:22.558
- Ghi chú: E3: tắt B 5 s, 3 lần: kết nối lại, mất gói, retry | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 589 dòng; gói nhận theo đường: {'relayed': 1132, 'direct': 581}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 9.3 | 1 | 560 | 560 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.9 | 0.0 | -67.7 | thật |
| B | 1 | 8.4 | 4 | 500 | 500 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.3 | 0.0 | -52.8 | thật |
| C | 2 | 9.2 | 1 | 550 | 548 | 2 | 99.64% | 3 | 25 | 0 | 3 | 182.2 | 0.0 | -61.3 | thật |
| **Tổng** | | | | 1610 | 1608 | 2 | 99.88% | 3 | 25 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 577 | 80.4 | 80 | 102 | 129 |
| B | 563 | 130.8 | 131 | 153 | 197 |
| C | 558 | 182.8 | 181.0 | 204 | 296 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 00:56:23.956 | 00:56:44.441 | 20.48 |
| B | 00:56:24.606 | 00:56:52.241 | 27.64 |
| C | 00:56:24.806 | 00:57:00.440 | 35.63 |
| C | 00:58:57.084 | 00:59:02.996 | 5.91 |
| B | 00:58:56.684 | 00:59:03.015 | 6.33 |
| C | 01:01:27.027 | 01:01:32.825 | 5.8 |
| B | 01:01:26.675 | 01:01:32.838 | 6.16 |
| B | 01:03:56.818 | 01:04:02.619 | 5.8 |
| C | 01:03:57.020 | 01:04:02.628 | 5.61 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, NEW_SESSION: 3, ROOT_STATS: 171, ROOT_SUMMARY: 58, SCAN_START: 1, SENSORS: 1
