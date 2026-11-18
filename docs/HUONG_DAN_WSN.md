# pico2w-wsn: build, nạp, ghi log, định dạng log

## Build / nạp / ghi log (Git Bash, ở thư mục `D:\DO_AN_2_PICO`)

```bash
bash tools/build.sh PAIR A FAST          # -> pico2w-wsn/build-PAIR-A-FAST/pico2w-wsn.uf2
bash tools/build.sh CHAIN CB FAST        # M2: C -> B -> R
bash tools/build.sh CHAIN CBA LOW_POWER  # C -> B -> A -> R, chế độ tiết kiệm
python tools/flash.py pico2w-wsn/build-PAIR-A-FAST/pico2w-wsn.uf2        # nạp cả 4 board (picotool -f, không cần BOOTSEL)
python tools/flash.py <uf2> R A                                          # chỉ nạp R và A
python tools/logcap.py <ten-lan-chay> --minutes 30 [--boards R A]        # ghi experiments/<ten>/<board>.log
python tools/summarize.py experiments/<ten-lan-chay>                     # tóm tắt PDR, RTT, sự kiện
python tools/reset_parent.py <ten> --node C --times 4 --first 60 --wait 50          # reset cha hiện tại của C
python tools/reset_parent.py <ten> --node C --times 4 --first 60 --wait 50 --cmd u  # cha của C tự cắt đường lên 15 s
```

## Gateway và phân tích (M4, thư mục `gateway/`)

```bash
python gateway/gateway.py <ten> --minutes 30 --note "..."   # đọc Root -> gateway/wsn.db + MQTT + experiments/<ten>/R.log
python gateway/gateway.py <ten> --replay                    # nạp lại experiments/<ten>/R.log vào DB (không publish MQTT)
python gateway/analyze.py <ten>                             # -> experiments/<ten>/analysis/ (metrics.md, .json, PNG)
python gateway/analyze.py --compare E7-FAST E7-LOW_POWER    # -> experiments/compare-.../ (bảng + biểu đồ so sánh)
python gateway/analyze.py --all                             # phân tích lại mọi run trong DB
python tools/exp.py E1 ... E8 [--dry-run]                   # chạy trọn một thực nghiệm (docs/HUONG_DAN_THUC_NGHIEM.md)
```

- `gateway/wsn.db` (SQLite, không commit; tạo lại được bằng `--replay` từ log gốc). Bảng: `runs`, `data`
  (cột `path` = direct/relayed), `local_data` (dữ liệu giả của Root, không tính PDR), `stats`, `events`.
- MQTT (Mosquitto, `localhost:1883`): `wsn/<node>/data`, `wsn/<node>/stats`, `wsn/R/local`, `wsn/event`.
  Xem trực tiếp: `"/c/Program Files/mosquitto/mosquitto_sub.exe" -t 'wsn/#' -v`.
- Gateway giữ cổng Root nên khi chạy gateway thì `logcap.py` chỉ ghi node (`--boards A B C`).
- Định nghĩa chỉ số: đầu file `gateway/analyze.py`. Mọi chỉ số chính chỉ dùng dữ liệu Root nhận.

## Lệnh test qua USB (mỗi lệnh một dòng)

Khi `logcap.py` / `gateway.py` đang giữ cổng: ghi lệnh vào `experiments/<ten>/_send_<board>.txt` — script gửi đi,
ghi `#SENT <lệnh>` vào log rồi xóa file. Board trả lời bằng dòng `CONFIG` / `TEST_DROP_UPLINK` (`CMD_UNKNOWN` nếu sai).

| Lệnh | Board | Tác dụng |
|---|---|---|
| `u` | node | tự cắt liên kết lên cha, ngừng quảng bá 15 s (mất liên kết tới cha, node vẫn sống) |
| `period <ms>` | node | đổi chu kỳ tạo DATA lúc chạy (E5), tối thiểu 20 ms |
| `ackdrop <%>` | Root | cố ý bỏ ACK_ROOT với xác suất % (E4); `DATA_RX` của gói đó có `"ack":-1` |
| `deny <ABC\|->` | Root (hoặc relay) | coi như không nghe thấy các node này: nhả nếu đang nối, không nhận lại. Giả lập node ở quá xa Root (MESH, E9). `deny -` = bỏ chặn |

- Mỗi cấu hình (topology, thứ tự, chế độ năng lượng) có thư mục build riêng.
- Commit trước khi build để dòng `BOOT` mang mã commit sạch (`"fw":"1f0f3f1"`); dấu `+` = có sửa chưa commit.
- Muốn bắt được dòng `BOOT`: chạy `logcap.py` trước (nền), rồi mới nạp. Script tự mở lại cổng khi board reset.
- Board không có trong topology đang build in `IDLE` và không quảng bá (vd. B, C khi build `PAIR A`).

## Topology MESH (M5, tự chọn đường)

`tools/build.sh MESH ABC FAST`. Mỗi node nhận Root **hoặc bất kỳ node tham gia nào khác** làm cha; cha chọn lúc chạy:
- Root nhận ngay mọi node đang quảng bá (node quảng bá = chưa có cha).
- Relay (node đã có đường lên Root) chỉ nhận một node "mồ côi" sau khi thấy nó quảng bá ≥ 1.5 s mà Root chưa nhận
  → ưu tiên nối thẳng Root, chỉ đi vòng khi Root không nghe thấy node đó. Relay MESH quét 30 ms mỗi 60 ms.
- Node mất cha thì nhả hết con (các con tự tìm đường khác), quảng bá lại.
- Chống vòng lặp: HELLO mang `path_mask` (các node từ cha lên Root). Con thấy chính mình trong đó thì cắt (`LOOP_REJECT`);
  cha không nhận tổ tiên của mình làm con. Số hop của node = số bit trong `path_mask` (dùng cho timeout ACK).
- Log mới: `PARENT` thêm `depth`, `path`; `SCAN` (relay MESH bật/tắt quét); `ORPHAN_SEEN` (relay bắt đầu đếm một node
  mồ côi); `DENY`; `CHILD_RELEASE` lý do `deny` / `no_parent`.
- Test 13/11 (4 board trên bàn, deny ở Root): chuyển đường 0.5–9.4 s, 0 vòng lặp, PDR 99.5% gồm cả 20 s cô lập hoàn toàn
  cố ý; ngoài lúc cô lập không mất gói.

## Vai trò

| Board | Serial | node_id |
|---|---|---|
| R | `050BACC7163712E4` | 0 |
| A | `99018494FD71AB17` | 1 |
| B | `40BEA7129EAAA081` | 2 |
| C | `17BCEBA3D9D28BEF` | 3 |

Từ 12/11/2026 hai Pico của R và C đổi chỗ cho nhau (Pico 17BC… nằm trên bo node C mới). Log thực nghiệm trước ngày
này dùng bảng cũ (R = 17BC…, C = 050B…); tên vai trò trong log vẫn đúng.

Thứ tự (`WSN_ORDER`) ghi từ node lá về Root: `CHAIN CBA` = C → B → A → R. `DIAMOND CAB` = C → (A hoặc B), A → R, B → R.
`STAR ABC` = A, B, C → R (Root giữ 3 kết nối).

Đổi tuyến (DIAMOND): node con chọn cha nào kết nối tới trước. Mất cha (supervision timeout) thì quảng bá lại
và cha còn lại nhận. Relay mất đường lên cha thì nhả ngay các con có cha dự phòng (`child_alt_mask`,
log `CHILD_RELEASE`) và không nhận lại chúng tới khi có cha. Ở CHAIN con không có cha dự phòng nên vẫn
giữ kết nối, gói chờ ở hàng đợi relay / bảng pending của node nguồn.

## Gói tin trên không (≤ 20 byte; chi tiết `pico2w-wsn/src/wsn_proto.h`)

Byte 0 = `(version << 4) | type`. Danh tính gói = `(source_id, boot_id, seq)`.

| Gói | Hướng | Byte |
|---|---|---|
| `DATA` (1) | lên | hdr, source_id, ttl, hop, flags, parent_id, boot_id(4), seq(4), ldr(2), current_ma×10(2), vbat_mv(2) = 20 |
| `ACK_ROOT` (2) | xuống | hdr, source_id, reserved(2), boot_id(4), seq(4) = 12 |
| `STATS` (3) | lên | hdr, source_id, rssi, parent_lost, boot_id(4), generated(4), retries(2), queue_full(2), rtt_avg_ms(2), current_avg×10(2) = 20 |
| `HELLO` (4) | xuống | hdr, parent_id = 2 |

`flags`: 1 = FAKE, 2 = RETRY, 4 = SENSOR_ERR, 8 = LOW_POWER.

## Log USB (mỗi dòng một JSON; chốt ở M1)

Mọi dòng có `t` (ms từ lúc board boot) và `type`. File log của `logcap.py` thêm giờ máy tính ở đầu dòng, cách bằng tab.
Tên node là một ký tự `R/A/B/C` (`?` = chưa biết).

**Root** (gateway đọc các dòng này)

| type | Trường chính |
|---|---|
| `BOOT` | state (START/BLE_READY), node, serial, boot, fw, topology, order, power, parent_mask, child_mask, child_alt_mask, depth, ina219, bd_addr |
| `SCAN_START` | children_mask, ci_ms, latency |
| `FOUND` | node, peer, rssi_dbm |
| `CONNECTED` | link=child, node, peer, interval_ms, latency |
| `CHILD_READY` | node, peer, setup_ms (kết nối → subscribe xong) |
| `DISCONNECTED` | link=child, node, reason (0x08 = supervision timeout), up_ms |
| `DATA_RX` | node, boot, seq, hop, ttl, flags, parent, via (con trực tiếp đưa gói lên), ldr, i_ma_x10, vbat_mv, check (FIRST/OK/GAP/LATE/DUP), ack (1 = đã xếp ACK, 0 = lỗi, -1 = test E4 cố ý bỏ) |
| `STATS_RX` | node, via, boot, gen, retries, qfull, parent_lost, rssi, rtt_avg_ms, i_avg_x10 (-32768 = không có INA219) |
| `ROUTE_CHANGE` | node, from, to, seq |
| `NEW_SESSION` | node, old_boot, new_boot (node đã reset) |
| `ROOT_STATS` | mỗi node: boot, first_seq, highest, unique, missing, dup, late, retry_rx, stats_rx, rssi, parent, hop |
| `ROOT_SUMMARY` | children, ack_fail, ack_test_drop, ack_drop_pct, boot, fw |
| `CONFIG` | ack_drop_pct (sau lệnh `ackdrop`) |
| `LOCAL_DATA` | dữ liệu giả của chính Root (không tính PDR) |
| Lỗi | `CONNECT_FAIL`, `CONNECT_TIMEOUT`, `GATT_ERROR`, `RX_BAD`, `DOWN_TX_FAIL`, `DOWN_QUEUE_FULL`, `CMD_UNKNOWN` |

`ACK_TX` của kế hoạch gộp vào trường `ack` của `DATA_RX` (đỡ gấp đôi số dòng log); chỉ khi lỗi mới có dòng riêng `DOWN_TX_FAIL`.

**Node** (chỉ đọc được khi cắm USB; ngoài thực địa dùng `STATS_RX` ở Root)

`BOOT`, `SENSORS`, `ADV_START`, `CONNECTED`/`DISCONNECTED` (link=parent), `SUBSCRIBED`, `PARENT` (parent, prev = cha lần trước), `DATA_TX`, `ACK_RX` (seq, rtt_ms, tries), `RETRY`, `DROP`, `NODE_STATS`; relay thêm `RELAY_STATS`, `TTL_DROP`, `RELAY_DUP`, `QUEUE_FULL`, `ACK_NO_ROUTE`, `CHILD_RELEASE`; lệnh test: `TEST_DROP_UPLINK`, `TEST_HOLD_END`, `CONFIG` (data_period_ms, prev).

Node chỉ gửi lên khi đã nhận `HELLO` (biết cha), nên mọi `DATA` mang đúng `parent`.

## Tham số năng lượng (`wsn_config.cpp`)

| | FAST | LOW_POWER |
|---|---|---|
| Connection interval | 50 ms | 500 ms |
| Peripheral latency | 0 | 3 |
| Supervision timeout | 4 s | 10 s |
| Quảng bá | 100 ms | 1 s |
| Chu kỳ DATA / STATS | 1 s / 10 s | 5 s / 60 s |
| Timeout ACK_ROOT | 1 s × số hop | 5 s × số hop |
| Số lần gửi tối đa | 4 | 4 |
