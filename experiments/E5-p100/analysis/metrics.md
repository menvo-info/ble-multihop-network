# E5-p100

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T01:28:50.191 → 2026-11-13T01:34:50.451
- Ghi chú: E5: tăng tốc độ gửi: queue đầy, gói bỏ | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 350 dòng; gói nhận theo đường: {'direct': 1916, 'relayed': 3785}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 5.3 | 1 | 1894 | 1894 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.6 | 0.0 | -67.9 | thật |
| B | 1 | 5.3 | 1 | 1883 | 1883 | 0 | 100.0% | 0 | 0 | 0 | 0 | 129.5 | 0.0 | -51.8 | thật |
| C | 2 | 5.2 | 1 | 1874 | 1874 | 0 | 100.0% | 0 | 0 | 0 | 0 | 181.2 | 0.0 | -61.4 | thật |
| **Tổng** | | | | 5651 | 5651 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1911 | 78.9 | 79 | 101 | 174 |
| B | 1892 | 129.4 | 129.0 | 152 | 203 |
| C | 1885 | 181.2 | 181 | 204 | 259 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 01:28:52.101 | 01:29:12.554 | 20.45 |
| B | 01:28:52.201 | 01:29:19.954 | 27.75 |
| C | 01:28:52.204 | 01:29:28.554 | 36.35 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, ROOT_STATS: 99, ROOT_SUMMARY: 34, SCAN_START: 1, SENSORS: 1
