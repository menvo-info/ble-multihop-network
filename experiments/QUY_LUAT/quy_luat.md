# Quy luật thời gian của mạng (từ 18 lượt thực nghiệm)

Lượt: E1-mesh-2h, E1, E2-lan2, E2-mesh, E2-star, E2, E3-auto-lan2, E3-auto, E5-p100, E5-p200, E5-p50, E6-lan2, E6-u-lan2, E6-u, E6, E9-lan2, E9-lan3, E9

## 1. Khởi động → tham gia mạng (đồng hồ node, mỗi lần node khởi động / reset)

| Giai đoạn | TB (s) | Trung vị | p95 | Max | n |
|---|---|---|---|---|---|
| BOOT → bắt đầu quảng bá | 0.90 | 0.90 | 0.90 | 0.90 | 74 |
| quảng bá → được cha kết nối | 1.00 | 0.32 | 2.96 | 3.27 | 74 |
| kết nối → nhận HELLO (có cha, biết đường) | 1.22 | 1.19 | 1.39 | 1.44 | 74 |
| có cha → ACK đầu tiên từ Root | 0.14 | 0.15 | 0.20 | 0.30 | 74 |
| TỔNG: BOOT → ACK đầu tiên | 3.26 | 2.55 | 5.34 | 5.55 | 74 |

## 2. Node mất cha → có cha mới (node tự đo DISCONNECTED → PARENT)

| Topology | TB (s) | Trung vị | p95 | Max | n |
|---|---|---|---|---|---|
| CHAIN | 1.42 | 1.39 | 1.68 | 1.68 | 7 |
| DIAMOND | 6.35 | 1.43 | 16.65 | 17.14 | 46 |
| MESH | 4.08 | 3.27 | 7.78 | 8.03 | 30 |
| STAR | 1.45 | 1.45 | 1.57 | 1.57 | 2 |

## 3. ACK RTT theo số hop (node → Root → ACK về node)

| Hop (depth) | TB (ms) | Trung vị | p95 | Max | n |
|---|---|---|---|---|---|
| 1 | 82.49 | 81.00 | 104.00 | 1052.00 | 38960 |
| 2 | 130.63 | 130.00 | 153.00 | 245.00 | 12719 |
| 3 | 182.57 | 181.00 | 208.00 | 490.00 | 6989 |

Mỗi hop thêm (trung vị): 49 ms, 51 ms. ACK nhận ở lần gửi đầu: 99.67%.

## 4. Root thấy con kết nối lại (mất → sẵn sàng), theo topology và lý do ngắt

Lý do 0x08 = hết supervision timeout (con/cha mất hẳn), 0x16 = phía Root chủ động ngắt (lệnh deny), 0x13 = phía kia ngắt.

| Topology | Lý do | TB (s) | Trung vị | p95 | Max | n |
|---|---|---|---|---|---|---|
| DIAMOND | 0x08 | 2.83 | 1.42 | 7.45 | 7.45 | 16 |
| DIAMOND | 0x13 | 16.32 | 16.27 | 16.70 | 16.70 | 12 |
| MESH | 0x08 | 6.02 | 7.23 | 7.55 | 7.55 | 13 |
| MESH | 0x16 | 215.37 | 215.46 | 275.67 | 275.67 | 6 |
| STAR | 0x08 | 7.12 | 7.12 | 7.30 | 7.30 | 2 |

## 5. Đổi tuyến (gói cuối qua cha cũ → gói đầu qua cha mới, phía Root)

| Topology | TB (s) | Trung vị | p95 | Max | n |
|---|---|---|---|---|---|
| DIAMOND | 3.04 | 1.93 | 6.58 | 6.62 | 29 |
| MESH | 4.04 | 4.05 | 6.68 | 6.95 | 25 |
| STAR | 3.06 | 3.06 | 6.10 | 6.10 | 2 |

## 6. Chất lượng liên kết con → cha (đầu vào chi phí cho thuật toán đường ngắn nhất)

RTT là RTT đầu-cuối của node khi đi qua cha đó (gồm cả các hop phía trên). Tỉ lệ gửi lại = retries / gói tạo.

| Liên kết | Số lượt | RSSI TB (dBm) | RSSI độ lệch | RTT TB (ms) | Gói tạo | Gửi lại | Tỉ lệ gửi lại |
|---|---|---|---|---|---|---|---|
| A → B | 2 | -53.9 | 8.1 | 128 | 240 | 0 | 0.00% |
| A → C | 3 | -43.0 | 4.0 | 129 | 570 | 0 | 0.00% |
| A → R | 18 | -62.5 | 4.9 | 80 | 22074 | 21 | 0.10% |
| B → A | 12 | -47.4 | 6.3 | 130 | 10085 | 0 | 0.00% |
| B → C | 3 | -52.5 | 4.5 | 130 | 450 | 0 | 0.00% |
| B → R | 12 | -64.7 | 6.8 | 81 | 10300 | 18 | 0.17% |
| C → A | 7 | -42.4 | 4.8 | 131 | 1770 | 57 | 3.22% |
| C → B | 15 | -55.7 | 5.6 | 174 | 10665 | 95 | 0.89% |
| C → R | 6 | -67.0 | 4.9 | 81 | 8510 | 0 | 0.00% |

## 7. Đường ngắn nhất do Root tính (Dijkstra trên chi phí liên kết đo được)

Chi phí = 1 mỗi hop + (RSSI yếu hơn −70 dBm: 1 điểm / 10 dB) + 10 × tỉ lệ gửi lại.

| Liên kết | RSSI TB | Gửi lại | Chi phí |
|---|---|---|---|
| A → B | -53.9 | 0.00% | 1.00 |
| A → C | -43.0 | 0.00% | 1.00 |
| A → R | -62.5 | 0.10% | 1.01 |
| B → A | -47.4 | 0.00% | 1.00 |
| B → C | -52.5 | 0.00% | 1.00 |
| B → R | -64.7 | 0.17% | 1.02 |
| C → A | -42.4 | 3.22% | 1.32 |
| C → B | -55.7 | 0.89% | 1.09 |
| C → R | -67.0 | 0.00% | 1.00 |

**Mọi liên kết dùng được**

| Node | Đường | Tổng chi phí |
|---|---|---|
| A | A → R | 1.01 |
| B | B → R | 1.02 |
| C | C → R | 1.00 |

**Giả lập A mất liên kết thẳng tới Root (như lệnh deny A)**

| Node | Đường | Tổng chi phí |
|---|---|---|
| A | A → C → R | 2.00 |
| B | B → R | 1.02 |
| C | C → R | 1.00 |

**Giả lập A và B mất liên kết thẳng tới Root (deny AB)**

| Node | Đường | Tổng chi phí |
|---|---|---|
| A | A → C → R | 2.00 |
| B | B → C → R | 2.00 |
| C | C → R | 1.00 |
