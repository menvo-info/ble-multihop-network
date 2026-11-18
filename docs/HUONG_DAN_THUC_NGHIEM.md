# Hướng dẫn chạy thực nghiệm E1–E8

Mỗi thực nghiệm chạy bằng **một lệnh** `python tools/exp.py <E> ...` (Git Bash, thư mục `D:\DO_AN_2_PICO`).
Script tự: build → chạy gateway (Root → SQLite + MQTT + `R.log`) và logcap (log node) → nạp firmware → chờ
mạng ổn định 60 s → làm các thao tác theo lịch (tự động, hoặc in `>>>` kèm tiếng chuông khi cần bạn làm tay) →
hết giờ thì phân tích. Kết quả: `experiments/<run>/analysis/metrics.md` + biểu đồ PNG.
Xem trước lịch: thêm `--dry-run`. Tên run đã có log thì script từ chối chạy (không ghi đè log gốc), dùng `--tag`.

## Chuẩn bị chung

- [ ] 4 board cắm USB vào laptop (trừ khi thực nghiệm ghi khác); `python tools/flash.py` thấy đủ R, A, B, C.
- [ ] Mosquitto đang chạy (dịch vụ Windows `mosquitto`, tự khởi động cùng máy).
- [ ] Pin 18650 sạc đầy (≥ 4.1 V) cho E3, E7, E8.
- [ ] Code đã commit (dòng `BOOT` mang mã commit sạch).
- [ ] Không chạy `logcap.py` / `gateway.py` nào khác đang giữ cổng COM.

## Bảng thực nghiệm

| # | Lệnh | Thời gian | Bạn cần làm |
|---|---|---|---|
| E1 | `python tools/exp.py E1` | 31 phút | Không (để máy chạy) |
| E2 | `python tools/exp.py E2` | 31 phút | Không |
| E3 | `python tools/exp.py E3` | 10 phút | B chạy **pin, rút USB** (nạp trước, xem ghi chú); khi script nhắc `>>> TẮT công tắc B` thì tắt, 5 s sau nhắc `BẬT` thì bật (3 lần) |
| E3 (tự động) | `python tools/exp.py E3 --auto` | 10 phút | Không — reset B bằng picotool (khởi động lại ~1 s, không phải tắt 5 s) |
| E4 | `python tools/exp.py E4 --ackdrop 10`, rồi `--ackdrop 30` | 8 phút/lần | Không |
| E5 | `python tools/exp.py E5 --period 200`, `--period 100`, `--period 50` | 6 phút/lần | Không |
| E6 | `python tools/exp.py E6` và `python tools/exp.py E6 --cmd u` | 10 phút/lần | Không (reset cha của C / cha tự cắt đường lên Root) |
| E7 | `python tools/exp.py E7 --power FAST`, rồi `--power LOW_POWER` | 21 phút/lần | A, B **chạy pin, rút USB** (nạp trước, xem ghi chú) |
| E8 | xem mục E8 | ≥ 60 phút | Mang node ra thực địa |
| E9 | `python tools/exp.py E9` | 13 phút | Không — MESH: Root lần lượt `deny A`, `deny AB`, bỏ chặn, reset C, `deny BC`; node phải tự đi vòng |

So sánh sau khi chạy:

```bash
python gateway/analyze.py --compare E1 E2 --out E2-theo-hop            # RTT theo số hop
python gateway/analyze.py --compare E7-FAST E7-LOW_POWER --out E7-nang-luong
python gateway/analyze.py --compare E5-p200 E5-p100 E5-p50 --out E5-toc-do
```

## Ghi chú từng thực nghiệm

**Board chạy pin (E3, E7, E8): nạp trước rồi mới rút USB.** Board đã rút USB thì script không nạp được
(nó chỉ nạp board đang cắm và in cảnh báo). Thứ tự:
1. Cắm đủ USB, nạp đúng firmware: `python tools/flash.py pico2w-wsn/build-<TOPO>-<ORDER>-<POWER>/pico2w-wsn.uf2`
   (E3: `build-CHAIN-CBA-FAST`; E7: `build-CHAIN-CBA-FAST` rồi `build-CHAIN-CBA-LOW_POWER`; bản build có sẵn sau khi
   chạy `bash tools/build.sh CHAIN CBA LOW_POWER`).
2. Bật công tắc pin của board đó (đang có pin nên rút USB không làm board khởi động lại).
3. Rút USB, rồi chạy lệnh `exp.py` như bảng trên.

**E3 — mất kết nối.** Bản thủ công là đúng kịch bản (B tắt nguồn thật 5 s). Vì B rút USB nên không có `B.log`;
chỉ số lấy từ Root (khoảng gián đoạn của B và C, PDR, retry trong STATS) và từ `C.log` (C vẫn cắm USB).

**E4 — trùng gói / retry.** Root bỏ ACK theo xác suất từ phút 2 tới 1.5 phút trước khi hết. Bảng kết quả có dòng
"Test E4: Root cố ý bỏ N ACK; Root nhận M gói trùng (đã lọc)...". N và M có thể lệch 1–2: ACK bị bỏ có thể thuộc
gói gửi lại mà node đã nhận ACK của bản gốc, nên node không gửi thêm lần nữa.

**E5 — queue đầy.** Cả A, B, C đổi chu kỳ tạo DATA từ phút 2 tới phút 5. Xem cột "Queue đầy" (hàng đợi relay)
và "Mất" (gói bỏ ở node nguồn khi bảng chờ ACK 16 gói đầy).

**E6 — đổi tuyến.** 6 lần, mỗi 75 s. Bảng "Đổi tuyến" trong `metrics.md` có thời gian mỗi lần (nhận cuối qua
cha cũ → nhận đầu qua cha mới, đo tại Root). Đã thử ở M3: ~5.7–6.1 s khi cha bị reset (4 s là supervision timeout),
~1.3 s khi cha còn sống nhưng mất đường lên Root (`--cmd u`).

**E7 — năng lượng.** Khi cắm USB, board lấy điện từ USB nên INA219 (đo phía pin) gần như không thấy dòng.
Vì vậy A, B chạy pin, rút USB (thứ tự ở trên; mỗi chế độ nạp lại một lần); script chỉ ghi log node còn cắm (C). Dòng TB lấy từ gói STATS
mà Root nhận (cột "Dòng TB"). C chưa có INA219 nên không có số dòng. Hai lần chạy (FAST, LOW_POWER) phải cùng
vị trí đặt board. Lần đầu bật pin cũng là lúc kiểm tra INA219 đo dòng thật (mục cuối của M3).

**E8 — thực địa.**
1. Ở bàn: nạp topology muốn dùng, vd. `python tools/flash.py pico2w-wsn/build-DIAMOND-CAB-FAST/pico2w-wsn.uf2`.
2. Rút USB của A, B, C, bật pin; đặt các node ở vị trí đã chọn (ghi lại khoảng cách / vật cản, chụp ảnh).
3. Root cắm laptop: `python tools/exp.py E8 --no-flash --minutes 60 --tag <noi-do>` (CHAIN: thêm `--topo CHAIN --order CBA`).
4. Kết quả: PDR, RSSI theo thời gian (`rssi.png`), đổi tuyến, ước tính tuổi thọ pin (mặc định 2000 mAh;
   đổi bằng `python gateway/analyze.py <run> --battery-mah <dung lượng thật>`).

## Sau mỗi lần chạy

- Commit ngay: `git add experiments/<run> && git commit -m "E.. : ..."` (log gốc không sửa tay).
- `gateway/wsn.db` không commit; mất thì dựng lại: `python gateway/gateway.py <run> --replay` cho từng run.
