# E2-star

- Topology: STAR ABC, chế độ: FAST, fw: 624f4f9, nguồn: serial
- Thời gian: 2026-11-13T03:30:44.405 → 2026-11-13T04:01:44.940
- Ghi chú: E2: 1-3 hop, 30 phút: PDR, RTT theo số hop | STAR ABC FAST
- Dữ liệu cục bộ Root (không tính PDR): 1850 dòng; gói nhận theo đường: {'direct': 5517, 'relayed': 20}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.0 | 0.0 | -62.6 | thật |
| B | 0 | 30.3 | 1 | 1820 | 1820 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.1 | 0.0 | -68.8 | thật |
| C | 0 | 30.2 | 1 | 1810 | 1810 | 0 | 100.0% | 0 | 0 | 0 | 0 | 80.2 | 0.0 | -66.8 | thật |
| **Tổng** | | | | 5450 | 5450 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## ACK RTT đo trên node (log USB)

| Node | n | TB | Trung vị | p95 | Max |
|---|---|---|---|---|---|
| A | 1836 | 80.5 | 80.0 | 103 | 154 |
| B | 1829 | 80.6 | 81 | 103 | 155 |
| C | 1820 | 80.6 | 81.0 | 103 | 153 |

## Kết nối lại (Root thấy con trực tiếp)

| Node | Mất lúc | Sẵn sàng lại | Thời gian (s) | Lý do |
|---|---|---|---|---|
| B | 03:31:07.333 | 03:31:14.272 | 6.94 | 0x08 |
| C | 03:31:15.282 | 03:31:22.585 | 7.3 | 0x08 |

## Đổi tuyến

| Node | Từ | Sang | Nhận cuối qua cha cũ | Nhận đầu qua cha mới | Thời gian (s) |
|---|---|---|---|---|---|
| B | A | R | 03:31:00.562 | 03:31:00.587 | 0.03 |
| C | B | R | 03:31:02.885 | 03:31:08.986 | 6.1 |

## Khoảng gián đoạn (> 3 × 1.0 s không nhận gói mới)

| Node | Từ | Tới | Dài (s) |
|---|---|---|---|
| B | 03:30:46.424 | 03:31:00.534 | 14.11 |
| C | 03:30:46.925 | 03:31:00.540 | 13.62 |
| A | 03:30:46.775 | 03:31:06.710 | 19.93 |
| C | 03:31:02.885 | 03:31:08.986 | 6.1 |
| B | 03:31:02.435 | 03:31:14.425 | 11.99 |
| C | 03:31:10.885 | 03:31:22.689 | 11.8 |

## Số sự kiện Root

BOOT: 2, CHILD_READY: 5, CONNECTED: 5, DISCONNECTED: 2, FOUND: 5, NEW_SESSION: 2, ROOT_STATS: 552, ROOT_SUMMARY: 184, ROUTE_CHANGE: 2, SCAN_START: 1, SENSORS: 1
