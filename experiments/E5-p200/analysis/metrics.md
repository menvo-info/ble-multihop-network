# E5-p200

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T01:22:42.867 → 2026-11-13T01:28:43.103
- Ghi chú: E5: tăng tốc độ gửi: queue đầy, gói bỏ | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 349 dòng; gói nhận theo đường: {'relayed': 2094, 'direct': 1057}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 5.3 | 1 | 1035 | 1035 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.6 | 0.0 | -69.3 | thật |
| B | 1 | 5.3 | 1 | 1037 | 1037 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.2 | 0.0 | -52.6 | thật |
| C | 2 | 5.2 | 1 | 1027 | 1027 | 0 | 100.0% | 0 | 0 | 0 | 0 | 181.4 | 0.0 | -61.2 | thật |
| **Tổng** | | | | 3099 | 3099 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1052 | 79.5 | 79.0 | 102 | 146 |
| B | 1046 | 130.9 | 130.0 | 153 | 203 |
| C | 1038 | 181.6 | 181.0 | 204 | 301 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 01:22:44.870 | 01:23:05.067 | 20.2 |
| B | 01:22:45.520 | 01:23:12.817 | 27.3 |
| C | 01:22:44.920 | 01:23:21.166 | 36.25 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, ROOT_STATS: 99, ROOT_SUMMARY: 34, SCAN_START: 1, SENSORS: 1
