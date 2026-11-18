# Nghiên cứu cơ chế ngủ cho node: thức → đo → gửi → ngủ

Trạng thái 13/11/2026: đã tìm hiểu xong. Firmware mẫu `tools/sleepnode` và máy thu `tools/sleep_rx.py` **đã build,
chưa nạp và chưa đo trên phần cứng** (đêm 13/11 cả 4 board đang chạy thực nghiệm). Mọi con số dòng điện ở mục 5 là
**ước tính**. Số thật lấy từ thí nghiệm S1–S4 ở mục 6.

## 1. Vì sao node hiện tại tốn pin

Firmware mạng (`pico2w-wsn`) giữ kết nối BLE liên tục:
- RP2350 chạy 150 MHz suốt thời gian, vì BTstack (phần host BLE) chạy trên CPU.
- CYW43439 phục vụ mọi sự kiện kết nối (50 ms ở FAST, 500 ms ở LOW_POWER).

`LOW_POWER` chỉ giãn các tham số BLE. Cả CPU lẫn radio đều không bao giờ được ngủ sâu.

Không thể vừa ngủ sâu vừa giữ kết nối. Khi RP2350 ngủ sâu thì BTstack dừng, và kết nối rớt sau supervision timeout.
Nghĩa là muốn ngủ sâu thì node phải **bỏ kết nối** và dùng mô hình *thức → gửi → ngủ*.

Giới hạn cấu trúc mạng:
- **Chỉ node lá ngủ được.** Root và relay phải thức để nghe con.
- Trong MESH, node nào cũng có thể thành relay. Vì vậy node ngủ phải được đánh dấu "lá", không nhận con.

## 2. Các mức ngủ của RP2350 (SDK 2.3.1, thư viện `pico_low_power`)

SDK 2.3.1 (đang dùng) đã có sẵn thư viện `pico_low_power`, gộp vào pico-sdk tháng 5/2026. Số đo chính thức của
Raspberry Pi trên board Pico 2, chưa tính radio:

| Mức | Còn chạy gì | Đánh thức bằng | Pico 2 (VSYS 5.2 V) | Pico 2 (3V3) |
|---|---|---|---|---|
| Sleep | Các clock được chọn; RAM giữ nguyên | Mọi ngắt | 5.9 mA | 6.9 mA |
| Dormant | Dừng XOSC/ROSC, chỉ chạy LPOSC cho timer; RAM giữ nguyên | AON timer, GPIO | 3.3 mA | 3.7 mA |
| **Pstate** | Tắt nguồn lõi và SRAM. Chỉ còn miền luôn có điện (POWMAN, AON timer, thanh ghi scratch) | AON timer, GPIO. **Thức dậy = chạy lại chương trình từ đầu** | **0.18–0.25 mA** | 0.08–0.14 mA |

Nguồn: tài liệu trong `pico_low_power/include/pico/low_power.h` của SDK.

Pstate thấp hơn Dormant khoảng 15 lần. Vì thức dậy là chạy lại từ đầu, mọi trạng thái cần giữ phải đặt trong:
- 8 thanh ghi scratch 32 bit của POWMAN (SDK dùng 2 thanh ghi cuối), hoặc
- vùng `__persistent_data` (giữ một bank SRAM).

Lưu ý từ cộng đồng:
- **LPOSC trôi nhiều.** Một người đo thấy ngủ 60 s nhưng thức sau khoảng 75 s (Pimoroni forum). Chu kỳ gửi vì vậy chỉ gần đúng. Root phải chấp nhận khoảng cách giữa hai gói dao động.
- **Pico 2 W khó xuống thấp bằng Pico 2** (Stanford, MicroPython). Phần radio là nguyên nhân, nên phải tắt hẳn CYW43439 trước khi ngủ (mục 3).
- **USB bị ngắt mỗi lần ngủ sâu.** Không xem log qua cổng COM được, nên số liệu phải lấy qua sóng (máy thu BLE).

## 3. Radio CYW43439

- **Tắt hẳn được.** `cyw43_arch_deinit()` gọi `cyw43_deinit()`, hàm này kéo chân **WL_REG_ON (GPIO23)** xuống thấp. Đã đọc mã nguồn `lib/cyw43-driver/src/cyw43_ctrl.c` để xác nhận.
- **Mỗi lần bật lại tốn thời gian.**
  - `cyw43_arch_init()` + `hci_power_control(ON)` phải nạp lại firmware cho chip qua SPI. Ước tính vài trăm ms.
  - Đây là phần tốn năng lượng nhất của một lần thức.
  - Firmware mẫu tự đo thời gian thức (`awake_ms`) và báo về trong gói kế tiếp.
- **Rủi ro bật/tắt lặp lại.** Chưa có báo cáo rõ cho Pico. Có báo cáo rò bộ nhớ khi khởi tạo lại BT stack trên chip Infineon.
  - Ở chế độ PSTATE, chip khởi động lại từ đầu mỗi chu kỳ, nên không bị rủi ro này.
  - Chế độ DORMANT của firmware mẫu thì cố ý khởi tạo lại trong cùng chương trình để kiểm tra vấn đề này.
- Raspberry Pi chưa công bố dòng của Bluetooth trên Pico W ("chưa đo", trả lời trên forum). Cần tự đo.

## 4. Ba phương án

| | (A) Giữ kết nối, CPU ngủ nhẹ / hạ xung nhịp | (B) Thức → kết nối → gửi + ACK → ngắt → ngủ | (C) Thức → **phát quảng bá** → ngủ (đã làm mẫu) |
|---|---|---|---|
| Ý tưởng | Như hiện tại. Giữa các sự kiện BLE thì CPU vào Sleep, hoặc hạ 150 → 48 MHz | Dùng giao thức hiện có (DATA/ACK_ROOT); mỗi chu kỳ kết nối lại | Số liệu nằm trong gói quảng bá không kết nối (ADV_NONCONN_IND). Ai nghe được thì nhận |
| Mức ngủ | Sleep (~6 mA + radio) | Pstate | Pstate |
| Thời gian thức mỗi lần | luôn thức | Dài: bật radio + chờ cha quét thấy + kết nối + tìm dịch vụ + gửi + chờ ACK, ~2–4 s | Ngắn: bật radio + phát 0.3 s, ~0.6–1 s |
| Độ tin cậy | Có ACK, gửi lại | Có ACK, gửi lại | **Không có ACK.** Bù bằng phát lặp ~15 lần mỗi lần thức, và nhiều node cùng nghe |
| Đổi firmware mạng | Nhỏ | Lớn: cha phải chấp nhận con kết nối/ngắt liên tục (MESH đang có độ trễ nhận con 1.5 s) | Vừa: Root/relay quét liên tục, đổi gói quảng bá thành DATA |
| Tiết kiệm (ước tính) | ~20–40% | ~5–15 lần (chu kỳ 60 s) | **~30–40 lần (chu kỳ 60 s)** |

**Chọn phương án C** để làm mẫu: tiết kiệm nhất và ít đụng tới mạng đang chạy. Phương án A làm thêm sau, có thể áp dụng cho cả relay.

Phương án C hợp với MESH theo kiểu **anycast**:
- Gói quảng bá của node lá được Root hoặc bất kỳ relay nào đang thức nghe thấy chuyển lên.
- Không cần chọn cha, không cần đổi tuyến.
- Root đã lọc trùng theo `(node, boot, seq)`, nên nhiều relay cùng chuyển lên một gói cũng không sao.

## 5. Mô hình năng lượng (ước tính, chờ đo)

```
I_TB = (I_thức × T_thức + I_ngủ × (T_chu_kỳ − T_thức)) / T_chu_kỳ
```

Giả định chưa đo:
- Lúc thức: 0.8 s ở 35 mA.
- Lúc ngủ Pstate: 0.25 mA (số đo của Raspberry Pi), hoặc 0.5 mA nếu tính thêm cảm biến rò.
- Giữ kết nối: 30 mA.
- Pin 2000 mAh, dùng được 80%.

| Chu kỳ gửi | I_TB (ngủ 0.25 mA) | Tuổi thọ pin | I_TB (ngủ 0.5 mA) | Tuổi thọ pin |
|---|---|---|---|---|
| Giữ kết nối (hiện tại) | ~30 mA | ~2.2 ngày | | |
| 10 s | 3.0 mA | 22 ngày | 3.3 mA | 20 ngày |
| 60 s | 0.71 mA | 94 ngày | 0.96 mA | 69 ngày |
| 300 s | 0.34 mA | 195 ngày | 0.59 mA | 113 ngày |

Nhận xét:
- Chu kỳ ngắn thì **năng lượng lúc thức chiếm phần lớn**. Cần rút ngắn T_thức: phát ít lần hơn, đọc cảm biến song song lúc radio đang khởi động.
- Chu kỳ dài thì **dòng ngủ chiếm phần lớn**. Cần giảm rò từ phần cứng ngoài Pico:
  - **INA219** chạy liên tục ~1 mA. Firmware mẫu cho nó vào power-down trước khi ngủ, còn ~6 µA.
  - **Cầu phân áp LDR** nối thẳng 3V3, luôn có dòng chạy qua. Nên cấp nguồn LDR từ một chân GPIO và chỉ bật lúc đo.
  - **Mạch sạc / LED nguồn** trên board (nếu có) cũng rò.

## 6. Firmware mẫu và cách đo

**`tools/sleepnode/`** là firmware độc lập, không đụng `pico2w-wsn`. Build:

```
cd tools/sleepnode
cmake -S . -B build-PSTATE -G Ninja -DSLEEP_MODE=PSTATE -DSLEEP_PERIOD_MS=10000 -DSLEEP_ADV_MS=300
ninja -C build-PSTATE        # -> build-PSTATE/sleepnode.uf2 (cần PATH như tools/build.sh)
```

Chế độ:
- `PSTATE`: ngủ sâu nhất.
- `DORMANT`: giữ RAM, kiểm tra việc khởi tạo radio lại nhiều lần.
- `AWAKE`: chỉ tắt radio, CPU chờ bằng `sleep_ms`. Dùng làm mốc để tách phần tiết kiệm của CPU và của radio.

Thêm `-DSLEEP_LOG=1` để in log USB khi gỡ lỗi (tốn thêm 1.5 s mỗi lần thức).

Đã build sạch cả 3 chế độ, không cảnh báo.

Mỗi chu kỳ firmware làm như sau:
1. Đọc LDR và INA219 (điện áp pin).
2. Bật CYW43439 và phát gói quảng bá 0.3 s, mỗi 20 ms một lần.
3. Trong lúc thức, lấy mẫu dòng bằng INA219.
4. Tắt BTstack và radio, cho INA219 power-down, thả nổi các chân (trừ GPIO23 giữ thấp).
5. Vào Pstate tới đầu chu kỳ sau.

`seq`, `boot_id` và số đo lần thức trước lưu trong `powman_hw->scratch[0..3]`.

Gói quảng bá dài 28/31 byte. Phần Manufacturer data gồm:
- Mã công ty 0xFFFF (mã dành cho thử nghiệm) và chữ `SL`.
- Phiên bản, node, boot, seq, LDR, Vbat.
- Dòng TB và thời gian thức của **lần trước**.
- Chế độ và chu kỳ.

**`tools/sleep_rx.py`** là máy thu dùng Bluetooth laptop (thư viện `bleak`, đã cài). Nó:
- Lọc trùng và đếm số bản sao mỗi gói.
- Tính PDR, thời gian thức, dòng lúc thức, dòng TB và tuổi thọ pin.
- Ghi `packets.csv` và `summary.md`.

Đã thử phần giải mã và tóm tắt bằng gói giả, đúng bố cục byte của firmware.

Lưu ý khi đo:
- Dòng lúc ngủ phải đo bằng **đồng hồ vạn năng mắc nối tiếp với pin** (thang mA), vì lúc ngủ chip không đọc INA219 được.
- Pico phải **chạy pin và rút USB**. Cắm USB thì board lấy điện USB và số đo sai.

Thí nghiệm đề xuất (1 node, ví dụ A, chạy pin; laptop đặt cách 1–2 m):

| Mã | Firmware | Thời gian | Đo |
|---|---|---|---|
| S0 | `pico2w-wsn` hiện tại (= E7 FAST và LOW_POWER) | 20 phút mỗi chế độ | Dòng giữ kết nối (mốc so sánh) |
| S1 | sleepnode PSTATE, chu kỳ 10 s | 15 phút | PDR, T_thức, I_thức, I_ngủ (đồng hồ) |
| S2 | sleepnode PSTATE, chu kỳ 60 s | 30 phút | như S1; tuổi thọ pin ước tính |
| S3 | sleepnode DORMANT, chu kỳ 10 s | 15 phút | I_ngủ Dormant; radio bật/tắt ≥ 90 lần không treo |
| S4 | sleepnode AWAKE, chu kỳ 10 s | 10 phút | Phần tiết kiệm nhờ tắt radio (chưa ngủ CPU) |

```
python tools/sleep_rx.py --minutes 15 --out experiments/S1-PSTATE-10s --i-sleep-ua <số đo> --mah 2000
```

## 7. Bước tiếp theo

1. Đo S0–S4. Điền số thật vào mục 5.
2. Nếu S1 ổn:
   - Root và relay quét liên tục, đổi gói `SL` thành DATA. Thêm cờ `SLEEPY`; node nguồn là node lá; `hop` = 0 nếu Root nghe trực tiếp.
   - Cần thử việc quét liên tục song song với các kết nối đang có trên CYW43439. Đây là rủi ro chính.
3. Phương án A cho relay: CPU vào Sleep giữa các sự kiện BLE, hạ xung nhịp. Đo so với S0.
4. Phần cứng: cấp nguồn LDR từ GPIO; kiểm tra LED và mạch sạc có rò không.

## 8. Từ quy luật đo được đến lịch ngủ/thức (thiết kế)

Quy trình: chạy thực nghiệm → tìm quy luật → đặt lịch cho node thức dậy, nhờ node gần chuyển nhanh dữ liệu lên Root, rồi ngủ lại.

Nguồn số liệu:
- `tools/quy_luat.py` chạy trên 18 lượt E1–E9 (bỏ E4, vì E4 cố ý bỏ ACK). Kết quả ở `experiments/QUY_LUAT/quy_luat.md`.
- Thử firmware ngủ trên board A (cắm USB), kết quả ở `experiments/SLEEP-B-*`.

### 8.1 Quy luật đo được

| Quy luật | Số đo | Ý nghĩa cho lịch ngủ |
|---|---|---|
| Node khởi động → ACK đầu tiên từ Root (giữ kết nối BLE) | trung vị **2.55 s**, p95 5.34 s, max 5.55 s (n = 74) | Mỗi lần thức mà phải dựng lại kết nối thì tốn ít nhất ~2.5 s |
| ↳ khởi động → bắt đầu quảng bá | 0.90 s (cố định) | Thời gian khởi động radio. Bản firmware mạng còn chờ USB tới 3 s, chạy pin thì phải bỏ đoạn chờ này |
| ↳ quảng bá → được cha kết nối | trung vị 0.32 s, p95 2.96 s | Phụ thuộc lúc cha đang quét. Cha thức sẵn, quét dày thì nhanh |
| ↳ kết nối → nhận HELLO (biết đường) | 1.19 s (p95 1.39 s) | Chi phí tìm dịch vụ GATT + đăng ký, ổn định |
| ↳ có cha → ACK đầu tiên | 0.15 s | |
| ACK RTT theo hop | 81 / 130 / 181 ms (hop 1/2/3), **mỗi hop thêm ~50 ms**, p95 104 / 153 / 208 ms | Chuyển tiếp qua node gần rất nhanh so với thời gian thức. Cái tốn là dựng kết nối |
| Node mất cha → có cha mới (MESH) | trung vị 3.27 s, p95 7.78 s | Nếu đường thay đổi giữa hai lần thức, cửa sổ thức phải chừa thêm khoảng này |
| ACK nhận ngay lần gửi đầu | 99.67 % | Liên kết trong phòng thí nghiệm rất tốt |
| **Node ngủ sâu (PSTATE), phát quảng bá không kết nối** | **thức 1.252 s mỗi chu kỳ** (1251–1257 ms, 100 chu kỳ), trong đó ~0.9 s là khởi động radio, 0.3 s là phát | Rẻ hơn dựng kết nối khoảng 2 lần, và không phụ thuộc cha |
| Độ chính xác chu kỳ khi ngủ PSTATE | đặt 10 s, đo được **10.11 s** (+1.1 %) | Thời gian đệm khi đồng bộ: ~1–2 % chu kỳ (60 s → ~1 s) |
| PDR quảng bá (laptop thu) | 100/100, nhưng chỉ ~2.1 bản sao mỗi gói (min 1) | Windows quét thưa. Máy thu là Pico quét liên tục sẽ bắt được nhiều hơn, cần đo lại với Root |

### 8.2 Hệ quả thiết kế

1. **Không dựng lại kết nối BLE mỗi lần thức.** Một vòng thu dữ liệu cho cây 3 tầng phải dựng lần lượt từng tầng: ~2.5 s cộng ~1.3 s mỗi tầng tiếp theo, tức khoảng 5–8 s thức cho mọi node. Phát quảng bá chỉ cần ~1.25 s.
2. **Root luôn thức** (cắm điện) và làm "nhạc trưởng". Root phát **beacon** gồm:
   - thời điểm thức kế tiếp, để đồng bộ;
   - danh sách gói đã nhận ở vòng trước, thay cho ACK;
   - **bảng đường đi** do Root tính.
3. **Đường đi ngắn nhất do Root tính**:
   - Root dựng đồ thị từ bảng chất lượng liên kết (mục 6 của `quy_luat.md`) và chạy Dijkstra. Chi phí mỗi liên kết = 1 (một hop) + phạt RSSI yếu + phạt tỉ lệ gửi lại.
   - Root gửi xuống cho mỗi node "ai chuyển tiếp cho bạn". Chỉ relay được chỉ định mới phát lại gói của con, nên không bị lụt gói trùng.
   - Với dữ liệu trong phòng thí nghiệm, mọi liên kết thẳng tới Root đều tốt: A→R 0.10 % gửi lại, B→R 0.17 %, C→R 0 %. Vì vậy Dijkstra sẽ chọn **hình sao (mọi node nối thẳng Root)**. Relay chỉ có ý nghĩa khi node ở xa thật (thực nghiệm E8 thực địa) hoặc khi bị chặn (E9).
   - **Cần chạy E8 để có liên kết yếu thật** thì thuật toán mới thể hiện được giá trị.
4. **Lịch một vòng (đề xuất, chu kỳ T)**:
   - Mọi node thức sớm hơn lịch một khoảng đệm g ≈ 2 % × T.
   - Node nghe beacon của Root, hoặc của relay phát lại, để chỉnh giờ.
   - Node lá phát dữ liệu 0.3 s. Relay được chỉ định phát lại trong 0.3 s kế tiếp.
   - Tất cả ngủ lại.
   - Ước tính mỗi vòng: lá thức ~1.3 s + g; relay thức ~1.6 s + g.
5. **Mức 2: gửi khi dữ liệu thay đổi** (đã cài vào `sleepnode`, `-DSLEEP_ADAPT=1`):
   - Mỗi chu kỳ chỉ thức để đo, không bật radio.
   - Radio chỉ bật khi LDR thay đổi quá `SLEEP_DELTA` so với lần gửi trước, hoặc đã `SLEEP_HEARTBEAT_N` chu kỳ chưa gửi (nhịp tim).
   - Gói định dạng v2 mang lý do gửi và số lần chỉ đo. Đã build, chưa thử trên phần cứng.
6. **Hướng giảm thời gian thức tiếp theo:** 0.9 / 1.25 s là khởi động CYW43439 (nạp firmware qua SPI). Thử tăng xung SPI, hoặc giữ radio ở chế độ ngủ của chính nó thay vì tắt hẳn, rồi so sánh năng lượng thực tế.

## Nguồn

- Raspberry Pi, pico-sdk 2.3.1, `src/rp2_common/pico_low_power/include/pico/low_power.h` (bảng dòng Sleep/Dormant/Pstate),
  `lib/cyw43-driver/src/cyw43_ctrl.c` (`cyw43_deinit` tắt WL_REG_ON).
- pico-sdk PR #2852 (thêm `pico_low_power`): https://github.com/raspberrypi/pico-sdk/pull/2852
- Pico SDK docs, `pico_low_power`: https://picodocs.pinout.xyz/group__pico__low__power.html
- Pimoroni forum, *RP2350 low power modes* (Dormant ~1.4–1.8 mA trên Pico 2 W, LPOSC trôi 60 s → 75 s):
  https://forums.pimoroni.com/t/rp2350-low-power-modes/27235
- Stanford (N. Parlante), *Low Power MicroPython Pico 2350* (Pico 2 W khó xuống thấp như Pico 2): https://cs.stanford.edu/people/nick/low-power-pico
- Silicon Labs, *Optimizing Current Consumption in BLE Devices* (giãn quảng bá 100 ms → 1 s giảm 93% dòng TB; CI và latency):
  https://docs.silabs.com/bluetooth/9.0.1/bluetooth-fundamentals-system-performance/current-consumption
- *BLE Power Optimization* (kết nối lại tốn 1–5 s, xung 5–10 mA; phát quảng bá rồi ngủ hợp với dữ liệu thưa):
  https://applied-ee.github.io/embedded/docs/networking/bluetooth-ble/ble-power-optimization/
- Raspberry Pi, *New functionality: Bluetooth for Pico W* (chưa công bố dòng BT): https://www.raspberrypi.com/news/new-functionality-bluetooth-for-pico-w/
- Infineon community, rò bộ nhớ khi khởi tạo lại BT stack: https://community.infineon.com/t5/Wi-Fi-Combo/memory-leak-if-re-init-bt-stack/m-p/160552
- MDPI *Overview and Evaluation of BLE*; CABLE (mất kết nối tốn
  năng lượng hơn giữ kết nối).
