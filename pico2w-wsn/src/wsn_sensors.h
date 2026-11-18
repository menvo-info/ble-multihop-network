// wsn_sensors.h — đọc LDR (ADC) và INA219 (I2C), tự dò thiếu mạch lúc khởi động.
#pragma once
#include <stdint.h>

struct SensorSample {
    uint16_t ldr;            // ADC thô 12 bit
    int16_t current_ma_x10;  // 0.1 mA, đã trừ offset của board
    uint16_t vbat_mv;
    uint8_t flags;           // FLAG_FAKE / FLAG_SENSOR_ERR
    bool has_current;        // có INA219 thật
};

void sensors_init();
bool sensors_has_ina219();
bool sensors_probe();  // dò lại INA219 nếu chưa thấy; true = có
SensorSample sensors_read(uint32_t seq);  // seq chỉ dùng để tạo giá trị giả thay đổi theo thời gian
