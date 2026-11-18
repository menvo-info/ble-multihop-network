# E4-ack10

- Topology: CHAIN CBA, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T01:06:29.002 → 2026-11-13T01:14:29.478
- Ghi chú: E4: Root bỏ ACK có kiểm soát: retry, gói trùng bị lọc | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 469 dòng; gói nhận theo đường: {'relayed': 899, 'direct': 461}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 30 | 30 | 0 | 0 | 83.2 | 0.0 | -67.9 | thật |
| B | 1 | 7.3 | 1 | 440 | 440 | 0 | 100.0% | 23 | 23 | 0 | 0 | 133.7 | 0.0 | -53.3 | thật |
| C | 2 | 7.2 | 1 | 430 | 430 | 0 | 100.0% | 25 | 25 | 0 | 0 | 189.2 | 0.0 | -61.2 | thật |
| **Tổng** | | | | 1310 | 1310 | 0 | 100.0% | 78 | 78 | 0 | | | | | |

Test E4: Root cố ý bỏ 78 ACK; Root nhận 78 gói trùng (đã lọc, không tính vào số gói nhận); node gửi lại 78 lần.

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 457 | 83.8 | 81 | 119 | 196 |
| B | 449 | 134.2 | 132 | 177 | 254 |
| C | 440 | 189.7 | 185.0 | 243 | 304 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 01:06:30.910 | 01:06:51.342 | 20.43 |
| B | 01:06:31.709 | 01:06:59.142 | 27.43 |
| C | 01:06:31.061 | 01:07:07.391 | 36.33 |

## Số sự kiện Root

BOOT: 1, CHILD_READY: 1, CONFIG: 2, CONNECTED: 1, FOUND: 1, ROOT_STATS: 135, ROOT_SUMMARY: 46, SCAN_START: 1
