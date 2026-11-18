// hwdiag.c — chẩn đoán phần cứng hộp node, in ra USB mỗi 2 s:
//  1. Mức logic SDA (GP26) / SCL (GP27) khi TẮT pull-up trong Pico: module INA219 có điện trở
//     kéo lên VCC của nó, nên cả hai đọc 1 nghĩa là INA219 có điện và dây SDA/SCL thông.
//  2. Quét I2C bằng bit-bang ở cả hai chiều (đúng và đảo SDA/SCL), địa chỉ 0x08–0x77.
//  3. Nếu thấy 0x40–0x4F: đọc thanh ghi cấu hình (sau reset = 0x399F) và điện áp bus.
//  4. LDR GP28/ADC2: đọc khi thả nổi / kéo lên / kéo xuống. Ba số gần nhau = chân có nối mạch
//     chia áp; nhảy theo pull = chân hở.
//  5. LED ngoài: xanh (GP16) và đỏ (GP17) đổi nhau mỗi lần in.
//  7. Lịch sử 40 mẫu (mỗi 2 s) điện áp pin + dòng qua shunt INA219, cờ P (chỉ pin) / U (có USB):
//     chạy pin một lúc rồi cắm USB lại (Pico không tắt) để xem dòng lúc chạy pin.
//  6. LED trên Pico nháy nhanh (4 lần / 2 s) = Pico đang chạy, kể cả khi chạy bằng pin.
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "pico/cyw43_arch.h"

#define PIN_A 26
#define PIN_B 27
#define LDR_GPIO 28
#define LED_GREEN 16
#define LED_RED 17
#define T_US 5

static uint sda, scl;
static void rel(uint p) { gpio_set_dir(p, GPIO_IN); }   // thả (pull-up kéo lên 1)
static void low(uint p) { gpio_set_dir(p, GPIO_OUT); gpio_put(p, 0); }
static void d(void) { sleep_us(T_US); }

static void bb_start(void) { rel(sda); rel(scl); d(); low(sda); d(); low(scl); d(); }
static void bb_stop(void) { low(sda); d(); rel(scl); d(); rel(sda); d(); }
static bool bb_write(uint8_t b) {   // trả về true nếu có ACK
    for (int i = 7; i >= 0; i--) {
        if (b & (1 << i)) rel(sda); else low(sda);
        d(); rel(scl); d();
        for (int k = 0; k < 100 && !gpio_get(scl); k++) d();  // clock stretching
        low(scl);
    }
    rel(sda); d(); rel(scl); d();
    bool ack = !gpio_get(sda);
    low(scl); d();
    return ack;
}
static uint8_t bb_read(bool ack) {
    uint8_t v = 0;
    rel(sda);
    for (int i = 0; i < 8; i++) { d(); rel(scl); d(); v = (v << 1) | gpio_get(sda); low(scl); }
    if (ack) low(sda); else rel(sda);
    d(); rel(scl); d(); low(scl); rel(sda);
    return v;
}
static bool read16(uint8_t addr, uint8_t reg, uint16_t *out) {
    bb_start();
    if (!bb_write(addr << 1) || !bb_write(reg)) { bb_stop(); return false; }
    bb_stop();
    bb_start();
    if (!bb_write((addr << 1) | 1)) { bb_stop(); return false; }
    uint8_t h = bb_read(true), l = bb_read(false);
    bb_stop();
    *out = (h << 8) | l;
    return true;
}

static void pins_setup(bool pull) {
    for (uint p = PIN_A; p <= PIN_B; p++) {
        gpio_init(p); gpio_set_dir(p, GPIO_IN); gpio_put(p, 0);
        if (pull) gpio_pull_up(p); else gpio_disable_pulls(p);
    }
}

static void scan(uint s, uint c, const char *name) {
    sda = s; scl = c;
    pins_setup(true);
    sleep_us(50);
    printf("  quet %s (SDA=GP%u SCL=GP%u):", name, s, c);
    if (!gpio_get(sda) || !gpio_get(scl)) { printf(" duong day bi keo xuong 0 (chap GND?)\n"); return; }
    int n = 0;
    for (uint8_t a = 0x08; a < 0x78; a++) {
        bb_start(); bool ok = bb_write(a << 1); bb_stop();
        if (ok) {
            n++; printf(" 0x%02X", a);
        }
    }
    printf(n ? "\n" : " khong thay chip nao\n");
    for (uint8_t a = 0x40; a <= 0x4F; a++) {
        bb_start(); bool ok = bb_write(a << 1); bb_stop();
        if (!ok) continue;
        uint16_t cfg = 0, bus = 0, sh = 0;
        bool r1 = read16(a, 0x00, &cfg), r2 = read16(a, 0x02, &bus), r3 = read16(a, 0x01, &sh);
        printf("    INA219? 0x%02X cfg=%s0x%04X (mac dinh 0x399F) bus=%umV shunt=%.2fmV\n", a,
               r1 ? "" : "LOI ", cfg, r2 ? (bus >> 3) * 4 : 0, r3 ? (int16_t)sh * 0.01 : 0.0);
    }
}

static uint16_t ldr_read(int mode) {
    gpio_disable_pulls(LDR_GPIO);
    if (mode == 1) gpio_pull_up(LDR_GPIO);
    if (mode == 2) gpio_pull_down(LDR_GPIO);
    sleep_ms(5);
    uint32_t s = 0;
    for (int i = 0; i < 16; i++) s += adc_read();
    gpio_disable_pulls(LDR_GPIO);
    return s / 16;
}

#define HIST 40
static uint16_t h_mv[HIST]; static int16_t h_sh[HIST]; static char h_src[HIST]; static uint32_t h_n;

int main(void) {
    stdio_init_all();
    bool led_ok = (cyw43_arch_init() == 0);
    adc_init();
    adc_gpio_init(LDR_GPIO);
    adc_select_input(2);
    gpio_init(LED_GREEN); gpio_set_dir(LED_GREEN, GPIO_OUT);
    gpio_init(LED_RED); gpio_set_dir(LED_RED, GPIO_OUT);
    for (uint32_t n = 0;; n++) {
        for (int k = 0; k < 8; k++) {   // nháy LED trên Pico
            if (led_ok) cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, !(k & 1));
            sleep_ms(250);
        }
        gpio_put(LED_GREEN, n & 1);
        gpio_put(LED_RED, !(n & 1));
        printf("=== HWDIAG lan %lu ===\n", (unsigned long)n);
        pins_setup(false);
        sleep_ms(2);
        printf("  muc logic khi TAT pull-up Pico: GP26=%d GP27=%d  (1 1 = INA219 co dien, day noi)\n",
               gpio_get(PIN_A), gpio_get(PIN_B));
        scan(PIN_A, PIN_B, "dung");
        scan(PIN_B, PIN_A, "dao ");
        {   // THU CAU HINH: chan = mac dinh 0x399F, le = cau hinh firmware mang 0x01FF
            uint16_t want = (n & 1) ? 0x01FF : 0x399F, c = 0, b = 0, sh2 = 0;
            sda = PIN_A; scl = PIN_B; pins_setup(true); sleep_us(50);
            bb_start(); bool w = bb_write(0x40 << 1) && bb_write(0x00) && bb_write(want >> 8) && bb_write(want & 0xFF); bb_stop();
            sleep_ms(200);
            read16(0x40, 0x00, &c); read16(0x40, 0x02, &b); read16(0x40, 0x01, &sh2);
            printf("  THU CFG ghi=0x%04X %s doc=0x%04X bus_raw=0x%04X bus=%umV shunt=%.2fmV\n", want, w ? "OK" : "LOI",
                   c, b, (b >> 3) * 4, (int16_t)sh2 * 0.01);
        }
        pins_setup(false);
        uint16_t f = ldr_read(0), u = ldr_read(1), dn = ldr_read(2);
        printf("  LDR GP28 ADC: tha noi=%u keo len=%u keo xuong=%u  (~%.2f V)\n", f, u, dn, f * 3.3 / 4095);
        sda = PIN_A; scl = PIN_B; pins_setup(true); sleep_us(50);
        uint16_t bus = 0, sh = 0;
        if (read16(0x40, 0x02, &bus) && read16(0x40, 0x01, &sh)) {
            int i = h_n++ % HIST;
            h_mv[i] = (bus >> 3) * 4; h_sh[i] = (int16_t)sh; h_src[i] = (led_ok && cyw43_arch_gpio_get(CYW43_WL_GPIO_VBUS_PIN)) ? 'U' : 'P';
        }
        printf("  LICH SU (cu -> moi, moi 2 s; P = chi chay pin, U = co USB):\n   ");
        uint32_t start = h_n > HIST ? h_n - HIST : 0;
        for (uint32_t j = start; j < h_n; j++) {
            int i = j % HIST;
            printf(" %c:%umV/%.1fmA", h_src[i], h_mv[i], h_sh[i] * 0.1);
            if ((j - start) % 6 == 5) printf("\n   ");
        }
        printf("\n");
    }
}
