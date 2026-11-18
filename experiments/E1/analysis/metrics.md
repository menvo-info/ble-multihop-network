# E1

- Topology: PAIR A, chế độ: FAST, fw: 9e034a2, nguồn: serial
- Thời gian: 2026-11-12T23:16:43.617 → 2026-11-12T23:47:43.707
- Ghi chú: E1: 1 hop, 30 phút: PDR, ACK RTT | PAIR A FAST
- Dữ liệu cục bộ Root (không tính PDR): 1849 dòng; gói nhận theo đường: {'relayed': 6, 'direct': 1841}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.1 | 0.0 | -60.7 | thật |
| **Tổng** | | | | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1836 | 79.5 | 79.0 | 102 | 154 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| A | 23:16:45.110 | 23:17:05.756 | 20.65 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 1, CONNECTED: 1, FOUND: 1, ROOT_STATS: 184, ROOT_SUMMARY: 184, SCAN_START: 1, SENSORS: 1
