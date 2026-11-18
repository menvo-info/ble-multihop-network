// wsn_config.h — danh tính board, topology và tham số năng lượng.
//
// Vai trò của board (A/B/C/Root) lấy từ serial flash; topology và chế độ năng lượng chọn lúc
// build (xem CMakeLists.txt). Từ topology, mỗi board biết: cha nào được phép (nó quảng bá cho
// ai kết nối), con nào được phép (nó quét và kết nối tới ai), và độ sâu (số hop tới Root).
#pragma once
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "pico/time.h"

static constexpr uint8_t ROOT_ID = 0;
static constexpr uint8_t MAX_NODE_ID = 3;  // R=0, A=1, B=2, C=3

struct PowerParams {
    uint16_t conn_interval;      // đơn vị 1.25 ms
    uint16_t conn_latency;       // số connection event con được phép bỏ qua
    uint16_t supervision_10ms;   // đơn vị 10 ms
    uint16_t adv_interval;       // đơn vị 0.625 ms
    uint32_t data_period_ms;     // chu kỳ tạo DATA
    uint32_t stats_period_ms;    // chu kỳ gửi STATS
    uint32_t ack_timeout_per_hop_ms;  // timeout chờ ACK_ROOT = giá trị này × độ sâu
    uint8_t max_tries;           // số lần gửi tối đa một gói (lần đầu + gửi lại)
    bool low_power;
};

struct WsnConfig {
    char serial[17];
    bool known;          // serial có trong bảng
    uint8_t id;          // 0 = Root
    char name;           // 'R', 'A', 'B', 'C'
    int16_t ina_offset_x10;  // offset INA219 của riêng board (0.1 mA), firmware trừ đi
    uint8_t parent_mask;     // bit i = được phép nhận node i làm cha
    uint8_t child_mask;      // bit i = được phép kết nối node i làm con
    uint8_t child_alt_mask;  // con có cha dự phòng (DIAMOND): relay mất cha thì nhả các con này
    uint8_t depth;           // số hop tới Root (Root = 0); 0 với node không tham gia. MESH: cập nhật theo HELLO
    uint8_t path_mask;       // MESH: bit i = node i nằm trên đường từ mình lên Root (gồm Root); 0 = chưa có đường
    bool mesh;               // topology MESH: cha/con chọn động, không cố định lúc build
    PowerParams pw;
};

extern WsnConfig g_cfg;
extern uint32_t g_boot_id;

void config_init();
bool cfg_is_root();
bool cfg_has_parent();
bool cfg_has_children();
char node_name(uint8_t id);
void cfg_set_path(uint8_t path_mask);  // MESH: cha mới báo đường lên Root (HELLO)

static inline uint32_t now_ms() { return to_ms_since_boot(get_absolute_time()); }

// Một dòng log = một đối tượng JSON, luôn có "t" (ms từ lúc boot) và "type".
// Ví dụ: LOGJ("DATA_RX", "\"node\":\"%c\"", 'A')  ->  {"t":1234,"type":"DATA_RX","node":"A"}
#define LOGJ(type, fmt, ...) \
    printf("{\"t\":%" PRIu32 ",\"type\":\"" type "\"," fmt "}\n", now_ms(), ##__VA_ARGS__)
