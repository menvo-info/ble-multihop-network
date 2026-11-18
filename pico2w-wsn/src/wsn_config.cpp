// wsn_config.cpp — bảng board (docs/HUONG_DAN_WSN.md, mục Vai trò) và tính topology từ WSN_ORDER.
#include "wsn_config.h"

#include <string.h>

#include "pico/unique_id.h"

WsnConfig g_cfg;
uint32_t g_boot_id;

struct BoardEntry {
    const char *serial;
    uint8_t id;
    char name;
    int16_t ina_offset_x10;  // INA219 của A đọc lệch ~ -0.8 mA
};

static const BoardEntry BOARDS[] = {
    // 12/11/2026: đổi Pico giữa R và C (Pico 17BC… gắn trên bo node C mới, Pico 050B… làm Root)
    {"050BACC7163712E4", 0, 'R', 0},
    {"99018494FD71AB17", 1, 'A', -8},
    {"40BEA7129EAAA081", 2, 'B', 0},
    {"17BCEBA3D9D28BEF", 3, 'C', 0},
};

char node_name(uint8_t id) {
    static const char NAMES[] = "RABC";
    return id <= MAX_NODE_ID ? NAMES[id] : '?';
}

static int id_of(char name) {
    for (uint8_t i = 0; i <= MAX_NODE_ID; i++)
        if (node_name(i) == name) return i;
    return -1;
}

// Tính cha được phép của mọi node từ topology + WSN_ORDER (thứ tự từ lá về Root).
static void build_topology(uint8_t parents[MAX_NODE_ID + 1]) {
    const char *order = WSN_ORDER;
    int n = (int)strlen(order);
    int ids[MAX_NODE_ID + 1];
    for (int i = 0; i < n && i <= MAX_NODE_ID; i++) ids[i] = id_of(order[i]);
    for (int i = 0; i <= MAX_NODE_ID; i++) parents[i] = 0;

#if defined(WSN_TOPOLOGY_PAIR) || defined(WSN_TOPOLOGY_CHAIN)
    // order[0] -> order[1] -> ... -> order[n-1] -> R
    for (int i = 0; i < n; i++) {
        if (ids[i] < 0) continue;
        int parent = (i + 1 < n) ? ids[i + 1] : ROOT_ID;
        parents[ids[i]] = (uint8_t)(1u << parent);
    }
#elif defined(WSN_TOPOLOGY_STAR)
    for (int i = 0; i < n; i++)
        if (ids[i] >= 0) parents[ids[i]] = 1u << ROOT_ID;
#elif defined(WSN_TOPOLOGY_DIAMOND)
    // order = "XYZ": X -> (Y hoặc Z), Y -> R, Z -> R
    if (n == 3) {
        parents[ids[0]] = (uint8_t)((1u << ids[1]) | (1u << ids[2]));
        parents[ids[1]] = 1u << ROOT_ID;
        parents[ids[2]] = 1u << ROOT_ID;
    }
#elif defined(WSN_TOPOLOGY_MESH)
    // order = các node tham gia (vd "ABC"): mỗi node nhận Root hoặc bất kỳ node tham gia nào khác làm cha.
    // Cha thật chọn lúc chạy; chống vòng lặp bằng path_mask trong HELLO (wsn_uplink / wsn_downlink).
    uint8_t all = 0;
    for (int i = 0; i < n; i++)
        if (ids[i] > 0) all |= (uint8_t)(1u << ids[i]);
    for (int i = 0; i < n; i++)
        if (ids[i] > 0) parents[ids[i]] = (uint8_t)((1u << ROOT_ID) | (all & ~(1u << ids[i])));
#else
#error "Unknown WSN_TOPOLOGY"
#endif
}

static uint8_t depth_of(const uint8_t parents[], uint8_t id) {
    uint8_t d = 0;
    while (id != ROOT_ID && d <= MAX_NODE_ID) {
        if (parents[id] == 0) return 0;  // không tham gia
        // Độ sâu tính theo cha có id nhỏ nhất (DIAMOND: hai cha cùng độ sâu)
        uint8_t p = 0;
        while (!(parents[id] & (1u << p))) p++;
        id = p;
        d++;
    }
    return d;
}

static PowerParams power_params() {
    PowerParams p{};
#if defined(WSN_POWER_LOW_POWER)
    p.conn_interval = 400;      // 500 ms
    p.conn_latency = 3;         // con được bỏ tối đa 3 event -> thức mỗi 2 s khi rảnh
    p.supervision_10ms = 1000;  // 10 s >= 2 × (1+3) × 0.5 s
    p.adv_interval = 1600;      // 1 s
    p.data_period_ms = 5000;
    p.stats_period_ms = 60000;
    p.ack_timeout_per_hop_ms = 5000;  // (1+latency) × CI × 2 chiều + dư
    p.max_tries = 4;
    p.low_power = true;
#else
    p.conn_interval = 40;       // 50 ms
    p.conn_latency = 0;
    p.supervision_10ms = 400;   // 4 s
    p.adv_interval = 160;       // 100 ms
    p.data_period_ms = 1000;
    p.stats_period_ms = 10000;
    p.ack_timeout_per_hop_ms = 1000;
    p.max_tries = 4;
    p.low_power = false;
#endif
    return p;
}

void config_init() {
    pico_get_unique_board_id_string(g_cfg.serial, sizeof(g_cfg.serial));
    g_cfg.known = false;
    g_cfg.id = 0xFF;
    g_cfg.name = '?';
    for (const auto &b : BOARDS) {
        if (strcmp(b.serial, g_cfg.serial) == 0) {
            g_cfg.known = true;
            g_cfg.id = b.id;
            g_cfg.name = b.name;
            g_cfg.ina_offset_x10 = b.ina_offset_x10;
        }
    }
    g_cfg.pw = power_params();
    if (!g_cfg.known) return;

    uint8_t parents[MAX_NODE_ID + 1];
    build_topology(parents);
    g_cfg.parent_mask = parents[g_cfg.id];
    g_cfg.child_mask = 0;
    g_cfg.child_alt_mask = 0;
    for (uint8_t i = 0; i <= MAX_NODE_ID; i++) {
        if (!(parents[i] & (1u << g_cfg.id))) continue;
        g_cfg.child_mask |= (uint8_t)(1u << i);
        if (parents[i] & (parents[i] - 1)) g_cfg.child_alt_mask |= (uint8_t)(1u << i);  // >= 2 cha
    }
    g_cfg.depth = depth_of(parents, g_cfg.id);
    g_cfg.path_mask = 0;
#if defined(WSN_TOPOLOGY_MESH)
    g_cfg.mesh = true;
    if (!cfg_is_root()) g_cfg.child_alt_mask = g_cfg.child_mask;  // con nào cũng có đường khác: mất cha thì nhả hết
#else
    g_cfg.mesh = false;
#endif
}

void cfg_set_path(uint8_t path_mask) {
    g_cfg.path_mask = path_mask;
    uint8_t d = 0;
    for (uint8_t i = 0; i <= MAX_NODE_ID; i++)
        if (path_mask & (1u << i)) d++;
    if (d) g_cfg.depth = d;  // số node phía trên = số hop tới Root
}

bool cfg_is_root() { return g_cfg.known && g_cfg.id == ROOT_ID; }
bool cfg_has_parent() { return g_cfg.known && g_cfg.parent_mask != 0; }
bool cfg_has_children() { return g_cfg.known && g_cfg.child_mask != 0; }
