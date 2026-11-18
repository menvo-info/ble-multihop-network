// wsn_sensors.cpp — LDR trên GP28/ADC2, INA219 trên I2C1 (SDA GP26, SCL GP27) địa chỉ 0x40.
//
// Lúc khởi động thử đọc INA219. Không thấy -> board là "Pico trơn": mọi giá trị là giả và gói
// mang cờ FAKE (chỉ số mạng không phụ thuộc giá trị cảm biến). Có INA219 nhưng LDR đọc ~0
// -> LDR hỏng, gói mang cờ SENSOR_ERR. Mọi lệnh I2C có timeout để không treo vòng lặp BTstack.
#include "wsn_sensors.h"

#include "hardware/adc.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include "wsn_config.h"
#include "wsn_proto.h"

static i2c_inst_t *const I2C = i2c1;
static constexpr uint I2C_SDA = 26, I2C_SCL = 27;
static constexpr uint LDR_GPIO = 28, LDR_ADC_INPUT = 2;
static constexpr uint8_t INA219_ADDR = 0x40;
static constexpr float SHUNT_OHM = 0.1f;
static constexpr uint16_t LDR_BROKEN_BELOW = 12;  // ADC thô; chân hở / LDR hỏng đọc ~0–7, A lúc tối ~22
// 16 V bus, ±40 mV shunt (tối đa ~400 mA), bus 12 bit, shunt trung bình 128 mẫu, chạy liên tục.
static constexpr uint16_t INA219_CONFIG = (0u << 13) | (0u << 11) | (0x3u << 7) | (0xFu << 3) | 0x7u;

static bool s_ina = false;

static bool ina_write16(uint8_t reg, uint16_t v) {
    uint8_t buf[3] = {reg, (uint8_t)(v >> 8), (uint8_t)v};
    return i2c_write_timeout_us(I2C, INA219_ADDR, buf, 3, false, 3000) == 3;
}

static bool ina_read16(uint8_t reg, uint16_t *out) {
    uint8_t buf[2];
    if (i2c_write_timeout_us(I2C, INA219_ADDR, &reg, 1, true, 3000) != 1) return false;
    if (i2c_read_timeout_us(I2C, INA219_ADDR, buf, 2, false, 3000) != 2) return false;
    *out = (uint16_t)((buf[0] << 8) | buf[1]);
    return true;
}

void sensors_init() {
    i2c_init(I2C, 100 * 1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);
    adc_init();
    adc_gpio_init(LDR_GPIO);
    adc_select_input(LDR_ADC_INPUT);
    sensors_probe();
}

// Dò INA219: ghi thanh ghi cấu hình. Gọi lại định kỳ khi chưa thấy (mạch cấp nguồn chậm, lỏng dây).
bool sensors_probe() {
    if (s_ina) return true;
    uint8_t dummy;
    int rd = i2c_read_timeout_us(I2C, INA219_ADDR, &dummy, 1, false, 3000);
    s_ina = ina_write16(0x00, INA219_CONFIG);
    uint16_t cfg = 0;
    bool rb = s_ina && ina_read16(0x00, &cfg);
    LOGJ("SENSORS", "\"ina219\":%d,\"probe_rc\":%d,\"cfg\":%u,\"ldr\":%u", s_ina ? 1 : 0, rd, rb ? cfg : 0,
         adc_read());
    return s_ina;
}

bool sensors_has_ina219() { return s_ina; }

SensorSample sensors_read(uint32_t seq) {
    SensorSample s{};
    if (!s_ina) {
        // Pico trơn: giá trị giả có quy luật để dễ nhận ra trong log
        s.ldr = (uint16_t)(1000 + (seq % 16) * 10);
        s.current_ma_x10 = 0;
        s.vbat_mv = 0;
        s.flags = FLAG_FAKE;
        s.has_current = false;
        return s;
    }
    uint32_t sum = 0;
    for (int i = 0; i < 8; i++) sum += adc_read();
    s.ldr = (uint16_t)(sum / 8);
    if (s.ldr < LDR_BROKEN_BELOW) s.flags |= FLAG_SENSOR_ERR;

    uint16_t raw_shunt, raw_bus;
    if (ina_read16(0x01, &raw_shunt) && ina_read16(0x02, &raw_bus)) {
        // shunt LSB 10 uV; I(mA) = V(mV)/R(ohm) -> I×10 = raw×0.01/0.1×10 = raw
        float ma = (int16_t)raw_shunt * 0.01f / SHUNT_OHM;
        int32_t x10 = (int32_t)(ma * 10.0f) - g_cfg.ina_offset_x10;
        s.current_ma_x10 = (int16_t)x10;
        s.vbat_mv = (uint16_t)((raw_bus >> 3) * 4);  // bus LSB 4 mV
        s.has_current = true;
    } else {
        s.flags |= FLAG_SENSOR_ERR;
    }
    return s;
}
