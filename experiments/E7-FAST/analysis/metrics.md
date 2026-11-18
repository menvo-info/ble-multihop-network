# E7-FAST

- Topology: CHAIN CBA, chế độ: FAST, fw: a8a5ae2, nguồn: serial
- Thời gian: 2026-11-13T23:43:43.193 → 2026-11-14T00:04:43.483
- Ghi chú: E7: FAST vs LOW_POWER (bật pin): dòng TB, PDR, RTT | CHAIN CBA FAST
- Dữ liệu cục bộ Root (không tính PDR): 1261 dòng; gói nhận theo đường: {'direct': 1262, 'relayed': 2523}

## Theo node (gộp các phiên có >= 2 STATS, chỉ dữ liệu Root)

| Node | Hop | Phút | Phiên | Tạo | Nhận | Mất | PDR | Trùng | Retry | Queue đầy | Mất cha | RTT TB (ms) | Dòng TB (mA) | RSSI TB | Cảm biến |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 20.8 | 1 | 1250 | 1250 | 0 | 100.0% | 0 | 0 | 0 | 0 | 79.4 | 0.0 | -54.3 | thật |
| B | 1 | 20.8 | 1 | 1250 | 1250 | 0 | 100.0% | 0 | 0 | 0 | 0 | 129.5 | 33.7 | -48.0 | thật |
| C | 2 | 20.8 | 1 | 1250 | 1250 | 0 | 100.0% | 0 | 0 | 0 | 0 | 215.0 | 35.7 | -60.1 | thật |
| **Tổng** | | | | 3750 | 3750 | 0 | 100.0% | 0 | 0 | 0 | | | | | |

## Ước tính tuổi thọ pin (2000.0 mAh, dòng TB đo bằng INA219 phía pin)

| Node | Dòng TB (mA) | Ước tính (giờ) | (ngày) |
|---|---|---|---|
| B | 33.7 | 59 | 2.5 |
| C | 35.7 | 56 | 2.3 |

Ước tính thô = dung lượng / dòng TB; bỏ qua sụt dung lượng theo nhiệt độ, điện áp cắt và xung dòng ngắn INA219 không bắt được.

## Số sự kiện Root

ROOT_STATS: 381, ROOT_SUMMARY: 127
