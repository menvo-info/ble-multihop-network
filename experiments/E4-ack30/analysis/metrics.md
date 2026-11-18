# E4-ack30

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T01:14:35.998 → 2026-11-13T01:22:36.430
- Ghi chú: E4: Root bỏ ACK có kiểm soát: retry, gói trùng bị lọc | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 469 dòng; gói nhận theo đường: {'relayed': 899, 'direct': 461}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 134 | 134 | 0 | 0 | 80.2 | 0.0 | -67.4 | thật |
| B | 1 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 96 | 96 | 0 | 0 | 132.1 | 0.0 | -53.3 | thật |
| C | 2 | 7.2 | 1 | 430 | 430 | 0 | 100.0% | 118 | 118 | 0 | 0 | 181.3 | 0.0 | -61 | thật |
| **Tổng** | | | | 1310 | 1310 | 0 | 100.0% | 348 | 348 | 0 | | | | | |

Test E4: Root cố ý bỏ 353 ACK; Root nhận 348 gói trùng (đã lọc, không tính vào số gói nhận); node gửi lại 348 lần.

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 454 | 80.6 | 80.0 | 103 | 146 |
| B | 448 | 132.6 | 132.0 | 155 | 202 |
| C | 439 | 181.6 | 180 | 204 | 254 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 01:14:37.916 | 01:14:58.386 | 20.47 |
| B | 01:14:38.516 | 01:15:05.785 | 27.27 |
| C | 01:14:37.966 | 01:15:14.235 | 36.27 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONFIG: 2, CONNECTED: 1, FOUND: 1, ROOT_STATS: 135, ROOT_SUMMARY: 46, SCAN_START: 1, SENSORS: 1
