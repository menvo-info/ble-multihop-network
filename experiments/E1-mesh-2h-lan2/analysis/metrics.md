# E1-mesh-2h-lan2

- Topology: MESH ABC, chế độ: FAST, fw: a8a5ae2, nguồn: serial
- Thời gian: 2026-11-13T21:29:30.427 → 2026-11-13T23:29:30.907
- Ghi chú: E1: 1 hop, 30 phút: PDR, ACK RTT | MESH ABC FAST
- Dữ liệu cục bộ Root (không tính PDR): 7190 dòng; gói nhận theo đường: {'direct': 21557}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 119.3 | 1 | 7160 | 7160 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.3 | 0.0 | -45.9 | thật |
| B | 0 | 119.3 | 1 | 7160 | 7160 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.3 | 0.0 | -43.6 | thật |
| C | 0 | 119.2 | 1 | 7150 | 7150 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.5 | 0.0 | -43.2 | thật |
| **Tổng** | | | | 21470 | 21470 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| B | 7169 | 80.8 | 81 | 103 | 199 |
| C | 7161 | 80.9 | 81 | 104 | 153 |

## Kết nối lại (Root thấy con trực tiếp)

| Node | Mất lúc | Sẵn sàng lại | Thời gian (s) | Lý do |
|---|---|---|---|---|
| B | 21:29:53.417 | 21:30:00.551 | 7.13 | 0x08 |
| C | 21:30:01.392 | 21:30:08.169 | 6.78 | 0x08 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| B | 21:29:32.548 | 21:29:44.719 | 12.17 |
| C | 21:29:32.323 | 21:29:45.143 | 12.82 |
| A | 21:29:32.479 | 21:29:55.219 | 22.74 |
| B | 21:29:48.569 | 21:30:00.705 | 12.14 |
| C | 21:29:57.295 | 21:30:08.272 | 10.98 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 5, CONNECTED: 5, DISCONNECTED: 2, FOUND: 5, NEW_SESSION: 2, ROOT_STATS: 2156, ROOT_SUMMARY: 719, SCAN: 5, SCAN_START: 1, SENSORS: 1
