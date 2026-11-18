# E4-ack50

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T04:32:12.983 → 2026-11-13T04:40:13.514
- Ghi chú: E4: Root bỏ ACK có kiểm soát: retry, gói trùng bị lọc | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 469 dòng; gói nhận theo đường: {'relayed': 899, 'direct': 461}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 221 | 221 | 0 | 0 | 78.1 | 0.0 | -60.7 | thật |
| B | 1 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 223 | 223 | 0 | 0 | 129.0 | 0.0 | -39.3 | thật |
| C | 2 | 7.2 | 1 | 430 | 430 | 0 | 100.0% | 234 | 234 | 0 | 0 | 181.2 | 0.0 | -52.5 | thật |
| **Tổng** | | | | 1310 | 1310 | 0 | 100.0% | 678 | 678 | 0 | | | | | |

Test E4: Root cố ý bỏ 719 ACK; Root nhận 678 gói trùng (đã lọc, không tính vào số gói nhận); node gửi lại 678 lần.

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 443 | 78.5 | 79 | 101 | 105 |
| B | 434 | 129.5 | 129.0 | 153 | 193 |
| C | 427 | 181.9 | 181 | 205 | 252 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 04:32:14.937 | 04:32:35.365 | 20.43 |
| B | 04:32:15.487 | 04:32:42.864 | 27.38 |
| C | 04:32:14.987 | 04:32:51.415 | 36.43 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONFIG: 2, CONNECTED: 1, FOUND: 1, ROOT_STATS: 135, ROOT_SUMMARY: 46, SCAN_START: 1, SENSORS: 1
