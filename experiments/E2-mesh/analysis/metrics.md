# E2-mesh

- Topology: MESH ABC, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T02:28:13.405 → 2026-11-13T02:59:13.444
- Ghi chú: E2: 1-3 hop, 30 phút: PDR, RTT theo số hop | MESH ABC FAST
- Dữ liệu cục bộ Root (không tính PDR): 1849 dòng; gói nhận theo đường: {'relayed': 6, 'direct': 5535}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.7 | 0.0 | -62.2 | thật |
| B | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.4 | 0.0 | -67.8 | thật |
| C | 0 | 30.2 | 1 | 1810 | 1810 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.5 | 0.0 | -68.1 | thật |
| **Tổng** | | | | 5450 | 5450 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1836 | 80.1 | 80.0 | 103 | 153 |
| B | 1829 | 80.8 | 81 | 103 | 135 |
| C | 1820 | 80.9 | 81.0 | 104 | 146 |

## Kết nối lại (Root thấy con trực tiếp)

| Node | Mất lúc | Sẵn sàng lại | Thời gian (s) | Lý do |
|---|---|---|---|---|
| B | 02:28:36.312 | 02:28:43.581 | 7.27 | 0x08 |
| C | 02:28:44.237 | 02:28:51.771 | 7.53 | 0x08 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| C | 02:28:15.901 | 02:28:27.739 | 11.84 |
| B | 02:28:15.904 | 02:28:27.964 | 12.06 |
| A | 02:28:15.251 | 02:28:35.984 | 20.73 |
| B | 02:28:31.915 | 02:28:43.735 | 11.82 |
| C | 02:28:39.789 | 02:28:51.874 | 12.09 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 5, CONNECTED: 5, DISCONNECTED: 2, FOUND: 5, NEW_SESSION: 2, ROOT_STATS: 552, ROOT_SUMMARY: 184, SCAN: 5, SCAN_START: 1, SENSORS: 1
