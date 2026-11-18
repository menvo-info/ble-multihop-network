# E2-lan2

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T02:59:20.831 → 2026-11-13T03:30:20.876
- Ghi chú: E2: 1-3 hop, 30 phút: PDR, RTT theo số hop | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 1850 dòng; gói nhận theo đường: {'direct': 1848, 'relayed': 3654}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.2 | 0.0 | -62.7 | thật |
| B | 1 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 130.3 | 0.0 | -42.1 | thật |
| C | 2 | 30.2 | 1 | 1810 | 1810 | 0 | 100.0% | 0 | 0 | 0 | 0 | 180.5 | 0.0 | -51.0 | thật |
| **Tổng** | | | | 5450 | 5450 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1836 | 79.7 | 79.0 | 102 | 203 |
| B | 1829 | 130.8 | 131 | 153 | 200 |
| C | 1820 | 180.9 | 180.0 | 203 | 277 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 02:59:23.353 | 02:59:43.159 | 19.81 |
| B | 02:59:23.002 | 02:59:50.763 | 27.76 |
| C | 02:59:23.392 | 02:59:59.360 | 35.97 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, ROOT_STATS: 549, ROOT_SUMMARY: 184, SCAN_START: 1, SENSORS: 1
