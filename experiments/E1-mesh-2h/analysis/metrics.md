# E1-mesh-2h

- Topology: MESH ABC, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T04:40:19.944 → 2026-11-13T05:39:12.003
- Ghi chú: E1: 1 hop, 30 phút: PDR, ACK RTT | MESH ABC FAST
- Dữ liệu cục bộ Root (không tính PDR): 3519 dòng; gói nhận theo đường: {'relayed': 19, 'direct': 10527}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 58.2 | 1 | 3490 | 3490 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.8 | 0.0 | -58.6 | thật |
| B | 0 | 58.2 | 1 | 3490 | 3490 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.2 | 0.0 | -59.2 | thật |
| C | 0 | 58.0 | 1 | 3480 | 3480 | 0 | 100.0% | 0 | 0 | 0 | 0 | 81.0 | 0.0 | -66.3 | thật |
| **Tổng** | | | | 10460 | 10460 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 3511 | 80.3 | 80 | 103 | 179 |
| B | 3503 | 80.6 | 81 | 103 | 148 |
| C | 3495 | 81.5 | 81 | 104 | 156 |

## Kết nối lại (Root thấy con trực tiếp)

| Node | Mất lúc | Sẵn sàng lại | Thời gian (s) | Lý do |
|---|---|---|---|---|
| B | 04:40:42.904 | 04:40:50.023 | 7.12 | 0x08 |
| C | 04:40:50.854 | 04:40:58.309 | 7.46 | 0x08 |

## Đổi tuyến

| Node | Từ | Sang | Nhận cuối qua cha cũ | Nhận đầu qua cha mới | Thời gian (s) |
|---|---|---|---|---|---|
| B | A | R | 04:40:36.418 | 04:40:36.426 | 0.01 |
| C | B | R | 04:40:38.207 | 04:40:45.158 | 6.95 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| C | 04:40:22.062 | 04:40:36.356 | 14.29 |
| B | 04:40:21.611 | 04:40:36.367 | 14.76 |
| A | 04:40:21.961 | 04:40:42.282 | 20.32 |
| C | 04:40:38.207 | 04:40:45.158 | 6.95 |
| B | 04:40:38.557 | 04:40:50.126 | 11.57 |
| C | 04:40:46.057 | 04:40:58.412 | 12.36 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 5, CONNECTED: 5, DISCONNECTED: 2, FOUND: 5, NEW_SESSION: 2, ROOT_STATS: 1053, ROOT_SUMMARY: 351, ROUTE_CHANGE: 2, SCAN: 5, SCAN_START: 1, SENSORS: 1
