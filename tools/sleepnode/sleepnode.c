// sleepnode.c — node lá tiết kiệm năng lượng: THỨC -> ĐO -> PHÁT BLE -> NGỦ SÂU -> ...
//
// Mỗi chu kỳ (SLEEP_PERIOD_MS):
//   1. Thức dậy (PSTATE: chip khởi động lại từ đầu; DORMANT/AWAKE: chạy tiếp vòng lặp).
//   2. Đọc LDR + INA219 (điện áp pin, dòng).
//   3. Bật radio CYW43439, phát quảng bá BLE KHÔNG kết nối (ADV_NONCONN_IND) chứa số liệu trong
//      SLEEP_ADV_MS (~15 lần phát x 3 kênh). Máy thu (laptop tools/sleep_rx.py, sau này là Root) chỉ cần quét.
//   4. Tắt BTstack, tắt nguồn radio (cyw43_arch_deinit kéo WL_REG_ON xuống thấp), cho INA219 ngủ.
//   5. Ngủ tới đầu chu kỳ sau.
// Không giữ kết nối nên không có ACK: độ tin cậy dựa vào phát lặp nhiều lần trong một lần thức.
// Biến cần giữ qua giấc ngủ PSTATE (seq, boot_id, số đo lần thức trước) nằm trong thanh ghi scratch của
// POWMAN (miền luôn có điện). SDK dùng 2 thanh ghi cuối, ở đây dùng scratch[0..5].
#include <stdio.h>
#include <string.h>

#include "btstack.h"
#include "hardware/adc.h"
#include "hardware/i2c.h"
#include "hardware/powman.h"
#include "hardware/watchdog.h"
#include "pico/cyw43_arch.h"
#include "pico/low_power.h"
#include "pico/rand.h"
#include "pico/stdlib.h"
#include "pico/unique_id.h"

#if SLEEP_LOG
#define LOG(...) printf(__VA_ARGS__)
#else
#define LOG(...) do { } while (0)
#endif

#define MAGIC 0x534C4550u  // "SLEP"
#define ADV_ITV 32          // 20 ms (đơn vị 0.625 ms)
#define FMT_VER 2

enum { MODE_PSTATE = 1, MODE_DORMANT = 2, MODE_AWAKE = 3 };
#if defined(SLEEP_MODE_PSTATE)
#define MODE MODE_PSTATE
#elif defined(SLEEP_MODE_DORMANT)
#define MODE MODE_DORMANT
#else
#define MODE MODE_AWAKE
#endif

// ---- phần cứng hộp node (giống pico2w-wsn/src/wsn_sensors.cpp)
#define I2C_PORT i2c1
#define I2C_SDA 26
#define I2C_SCL 27
#define LDR_GPIO 28
#define LDR_ADC 2
#define INA_ADDR 0x40
#define INA_CFG_RUN ((0x3u << 7) | (0xFu << 3) | 0x7u)  // 12 bit bus, shunt TB 128 mẫu, liên tục
#define INA_CFG_OFF 0x0000u                             // chế độ power-down (~6 uA)

// ---- trạng thái giữ qua giấc ngủ
#define S_MAGIC 0   // MAGIC khi đã khởi tạo
#define S_SEQ 1     // số thứ tự gói kế tiếp
#define S_BOOT 2    // [15:0] boot_id (đổi khi cấp điện lại), [31:16] node id (ký tự)
#define S_PREV 3    // lần thức trước: [15:0] thời gian thức ms, [31:16] dòng TB lúc thức x10 mA (int16)
#define S_CYC 4     // số chu kỳ đã chạy từ lần nạp firmware này (dùng cho SLEEP_TEST_CYCLES)
#define S_ADAPT 5   // SLEEP_ADAPT: [15:0] LDR của lần GỬI gần nhất, [31:16] số lần thức chỉ đo kể từ lần gửi đó

// Mức 2 — chu kỳ tự thích nghi theo dữ liệu (SLEEP_ADAPT=1): mỗi chu kỳ vẫn thức để đo (rẻ, không bật radio),
// chỉ bật radio gửi khi LDR đổi quá SLEEP_DELTA so với lần gửi trước (sự kiện) hoặc đã SLEEP_HEARTBEAT_N chu kỳ
// chưa gửi (nhịp tim, để Root biết node còn sống). Dữ liệu đứng yên -> gần như chỉ tốn dòng ngủ.
#ifndef SLEEP_ADAPT
#define SLEEP_ADAPT 0
#endif
#ifndef SLEEP_DELTA
#define SLEEP_DELTA 40          // đơn vị ADC thô (0..4095), ~1%
#endif
#ifndef SLEEP_HEARTBEAT_N
#define SLEEP_HEARTBEAT_N 30    // 30 x 10 s = 5 phút
#endif
enum { REASON_ALWAYS = 0, REASON_CHANGE = 1, REASON_HEARTBEAT = 2 };

static const struct { const char *ser; char id; } BOARDS[] = {
    {"99018494FD71AB17", 'A'}, {"40BEA7129EAAA081", 'B'}, {"17BCEBA3D9D28BEF", 'C'}, {"050BACC7163712E4", 'R'},
};

static bool s_ina;
static int32_t s_i_sum_x10;
static uint32_t s_i_n;
static volatile int s_bt;  // 0 đang bật, 1 đang phát, 2 đã tắt
static uint8_t s_adv[31];
static uint8_t s_adv_len;
static btstack_packet_callback_registration_t s_hci_cb;

static bool ina_w(uint8_t reg, uint16_t v) {
    uint8_t b[3] = {reg, (uint8_t)(v >> 8), (uint8_t)v};
    return i2c_write_timeout_us(I2C_PORT, INA_ADDR, b, 3, false, 3000) == 3;
}

static bool ina_r(uint8_t reg, uint16_t *out) {
    uint8_t b[2];
    if (i2c_write_timeout_us(I2C_PORT, INA_ADDR, &reg, 1, true, 3000) != 1) return false;
    if (i2c_read_timeout_us(I2C_PORT, INA_ADDR, b, 2, false, 3000) != 2) return false;
    *out = (uint16_t)((b[0] << 8) | b[1]);
    return true;
}

// Cộng dồn một mẫu dòng (x10 mA) để tính dòng trung bình trong lúc thức.
static void sample_current(void) {
    uint16_t raw;
    if (s_ina && ina_r(0x01, &raw)) {
        s_i_sum_x10 += (int16_t)raw;  // LSB 10 uV / 0.1 ohm = 0.1 mA
        s_i_n++;
    }
}

static void sensors_on(void) {
    i2c_init(I2C_PORT, 400 * 1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);
    adc_init();
    adc_gpio_init(LDR_GPIO);
    adc_select_input(LDR_ADC);
    s_ina = ina_w(0x00, INA_CFG_RUN);
}

static void sensors_off(void) {
    if (s_ina) ina_w(0x00, INA_CFG_OFF);
    i2c_deinit(I2C_PORT);
}

static char node_id(void) {
    char ser[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
    pico_get_unique_board_id_string(ser, sizeof ser);
    for (unsigned i = 0; i < sizeof BOARDS / sizeof BOARDS[0]; i++)
        if (strcmp(ser, BOARDS[i].ser) == 0) return BOARDS[i].id;
    return '?';
}

static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

// Gói quảng bá: Flags + Manufacturer Specific (0xFFFF = mã thử nghiệm) "SL" + số liệu, 30/31 byte.
static void build_adv(char id, uint16_t boot, uint32_t seq, uint16_t ldr, uint16_t vbat_mv, uint32_t prev,
                      uint8_t reason, uint16_t skipped) {
    uint8_t *p = s_adv;
    *p++ = 2; *p++ = 0x01; *p++ = 0x06;
    *p++ = 26; *p++ = 0xFF;
    *p++ = 0xFF; *p++ = 0xFF;            // company id thử nghiệm
    *p++ = 'S'; *p++ = 'L';
    *p++ = FMT_VER;
    *p++ = (uint8_t)id;
    put16(p, boot); p += 2;
    put16(p, (uint16_t)seq); put16(p + 2, (uint16_t)(seq >> 16)); p += 4;
    put16(p, ldr); p += 2;
    put16(p, vbat_mv); p += 2;
    put16(p, (uint16_t)(prev >> 16)); p += 2;   // dòng TB lần thức trước x10 mA
    put16(p, (uint16_t)prev); p += 2;           // thời gian thức lần trước ms
    *p++ = (uint8_t)(MODE | (reason << 4));     // [3:0] chế độ ngủ, [7:4] lý do gửi
    put16(p, (uint16_t)(SLEEP_PERIOD_MS / 100)); p += 2;
    put16(p, skipped); p += 2;                  // số lần thức chỉ đo (không gửi) kể từ lần gửi trước
    s_adv_len = (uint8_t)(p - s_adv);
}

static void hci_handler(uint8_t type, uint16_t ch, uint8_t *packet, uint16_t size) {
    (void)ch; (void)size;
    if (type != HCI_EVENT_PACKET || hci_event_packet_get_type(packet) != BTSTACK_EVENT_STATE) return;
    uint8_t st = btstack_event_state_get_state(packet);
    if (st == HCI_STATE_WORKING) {
        bd_addr_t null_addr = {0};
        gap_advertisements_set_params(ADV_ITV, ADV_ITV, 0x03 /* ADV_NONCONN_IND */, 0, null_addr, 0x07, 0x00);
        gap_advertisements_set_data(s_adv_len, s_adv);
        gap_advertisements_enable(1);
        s_bt = 1;
    } else if (st == HCI_STATE_OFF) {
        s_bt = 2;
    }
}

// Một lần thức. Trả về false nếu radio không lên (khi đó vẫn ngủ để thử lại chu kỳ sau).
static bool radio_burst(void) {
    if (cyw43_arch_init()) return false;
    s_hci_cb.callback = hci_handler;
    hci_add_event_handler(&s_hci_cb);
    s_bt = 0;
    hci_power_control(HCI_POWER_ON);
    absolute_time_t to = make_timeout_time_ms(3000);
    while (s_bt == 0 && !time_reached(to)) { sample_current(); sleep_ms(5); }
    bool ok = s_bt == 1;
    if (ok) {
        absolute_time_t end = make_timeout_time_ms(SLEEP_ADV_MS);
        while (!time_reached(end)) { sample_current(); sleep_ms(5); }
    }
    hci_power_control(HCI_POWER_OFF);
    to = make_timeout_time_ms(500);
    while (s_bt != 2 && !time_reached(to)) sleep_ms(2);
    hci_remove_event_handler(&s_hci_cb);
    cyw43_arch_deinit();  // tắt nguồn CYW43439 (WL_REG_ON = 0)
    return ok;
}

static void go_sleep(uint32_t ms) {
    if (ms < 20) ms = 20;
#if MODE == MODE_PSTATE
    // Thả nổi mọi chân (I2C, LDR...) để rò rỉ thấp nhất, trừ WL_REG_ON (GPIO23): giữ thấp + kéo xuống
    // để CYW43439 chắc chắn tắt nguồn trong lúc ngủ.
    gpio_pull_down(23);
    low_power_set_pins_low_leakage_exclude_mask(1u << 23);
    low_power_pstate_for_ms(ms, NULL, NULL);  // không quay lại: thức dậy = chạy lại main()
    // Không vào được Pstate (lỗi) -> chờ thường rồi khởi động lại để giữ chu kỳ
    sleep_ms(ms);
    watchdog_reboot(0, 0, 0);
    while (true) tight_loop_contents();
#elif MODE == MODE_DORMANT
    low_power_dormant_for_ms(ms, DORMANT_CLOCK_SOURCE_DEFAULT, NULL);
#else
    sleep_ms(ms);
#endif
}

// Dấu khởi tạo đổi theo mỗi lần build: nạp bản mới (thanh ghi scratch vẫn còn từ bản cũ) thì khởi tạo lại.
static uint32_t build_magic(void) {
    const char *t = __DATE__ __TIME__ SLEEP_MODE_NAME;
    uint32_t h = MAGIC;
    while (*t) h = (h ^ (uint8_t)*t++) * 16777619u;
    return h;
}

// Hết số chu kỳ thử: thức hẳn, bật USB để máy tính đọc kết quả và nạp lại firmware mạng bằng picotool -f.
static void test_done(void) {
    stdio_init_all();
    while (true) {
        printf("{\"type\":\"SLEEP_TEST_DONE\",\"mode\":\"%s\",\"cycles\":%lu,\"seq\":%lu,\"prev_awake_ms\":%u}\n",
               SLEEP_MODE_NAME, (unsigned long)powman_hw->scratch[S_CYC], (unsigned long)powman_hw->scratch[S_SEQ],
               (unsigned)(powman_hw->scratch[S_PREV] & 0xFFFF));
        sleep_ms(1000);
    }
}

int main(void) {
#if SLEEP_LOG
    stdio_init_all();
    sleep_ms(1500);  // cho máy tính kịp mở cổng COM (chỉ khi gỡ lỗi)
#endif
    if (powman_hw->scratch[S_MAGIC] != build_magic()) {  // lần đầu chạy bản này (không phải thức dậy từ Pstate)
        powman_hw->scratch[S_MAGIC] = build_magic();
        powman_hw->scratch[S_CYC] = 0;
        powman_hw->scratch[S_SEQ] = 0;
        powman_hw->scratch[S_BOOT] = ((uint32_t)(uint8_t)node_id() << 16) | (get_rand_32() & 0xFFFF);
        powman_hw->scratch[S_PREV] = 0;
        powman_hw->scratch[S_ADAPT] = 0xFFFFu << 16;  // lần đầu: luôn gửi
    }
    while (true) {
#if SLEEP_TEST_CYCLES
        if (powman_hw->scratch[S_CYC] >= SLEEP_TEST_CYCLES) test_done();
        powman_hw->scratch[S_CYC]++;
#endif
        uint32_t t0 = to_ms_since_boot(get_absolute_time());
        uint32_t seq = powman_hw->scratch[S_SEQ];
        uint32_t boot = powman_hw->scratch[S_BOOT];
        s_i_sum_x10 = 0; s_i_n = 0;
        sensors_on();
        uint32_t sum = 0;
        for (int i = 0; i < 8; i++) sum += adc_read();
        uint16_t vbat = 0, raw;
        if (s_ina && ina_r(0x02, &raw)) vbat = (uint16_t)((raw >> 3) * 4);
        uint16_t ldr = (uint16_t)(sum / 8);
        uint8_t reason = REASON_ALWAYS;
        uint16_t skipped = (uint16_t)(powman_hw->scratch[S_ADAPT] >> 16);
#if SLEEP_ADAPT
        uint16_t last = (uint16_t)powman_hw->scratch[S_ADAPT];
        int d = (int)ldr - (int)last;
        if (d < 0) d = -d;
        if (skipped != 0xFFFF && d <= SLEEP_DELTA && skipped + 1 < SLEEP_HEARTBEAT_N) {
            // Dữ liệu đứng yên: chỉ đo rồi ngủ lại, không bật radio
            sensors_off();
            powman_hw->scratch[S_ADAPT] = ((uint32_t)(skipped + 1) << 16) | last;
            uint32_t used = to_ms_since_boot(get_absolute_time()) - t0;
            go_sleep(used < SLEEP_PERIOD_MS ? SLEEP_PERIOD_MS - used : 0);
            continue;
        }
        reason = (skipped == 0xFFFF || d > SLEEP_DELTA) ? REASON_CHANGE : REASON_HEARTBEAT;
#endif
        if (skipped == 0xFFFF) skipped = 0;
        build_adv((char)(boot >> 16), (uint16_t)boot, seq, ldr, vbat, powman_hw->scratch[S_PREV], reason, skipped);
        bool ok = radio_burst();
        sensors_off();
        powman_hw->scratch[S_SEQ] = seq + 1;
        powman_hw->scratch[S_ADAPT] = ldr;  // lần gửi mới: đếm lại số lần chỉ đo
        uint32_t now = to_ms_since_boot(get_absolute_time());
        // PSTATE: thời gian thức tính từ lúc chip chạy (t0 ~ 0); vài ms ROM khởi động không tính
        uint32_t awake = now - (MODE == MODE_PSTATE ? 0 : t0);
        int16_t i_avg = s_i_n ? (int16_t)(s_i_sum_x10 / (int32_t)s_i_n) : 0;
        powman_hw->scratch[S_PREV] = ((uint32_t)(uint16_t)i_avg << 16) | (awake > 0xFFFF ? 0xFFFF : awake);
        LOG("{\"type\":\"CYCLE\",\"seq\":%lu,\"ok\":%d,\"awake_ms\":%lu,\"i_avg_x10\":%d,\"vbat\":%u}\n",
            (unsigned long)seq, ok, (unsigned long)awake, i_avg, vbat);
        uint32_t used = now - t0;
        go_sleep(used < SLEEP_PERIOD_MS ? SLEEP_PERIOD_MS - used : 0);
    }
}
