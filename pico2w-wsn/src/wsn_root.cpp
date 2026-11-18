// wsn_root.cpp — xử lý ở Root: kiểm tra thứ tự / lọc trùng theo danh tính gói, gửi ACK_ROOT
// ngược về đúng con đã đưa gói lên, ghi log JSON (mỗi dòng một sự kiện) ra USB cho gateway.
//
// Kết quả kiểm tra mỗi gói DATA ("check"):
//   FIRST: gói đầu tiên của một phiên (source_id, boot_id)
//   OK   : seq = seq lớn nhất + 1
//   GAP  : seq lớn hơn mong đợi (có gói bị thiếu ở giữa, có thể tới sau nhờ gửi lại)
//   LATE : gói bị thiếu trước đó nay tới (nhờ gửi lại)
//   DUP  : đã nhận rồi (vẫn gửi ACK lại vì ACK trước có thể đã mất)
// Gói DUP không tính vào số gói duy nhất. Root gửi ACK cho mọi gói DATA hợp lệ.
#include <string.h>

#include "wsn_config.h"
#include "wsn_net.h"
#include "wsn_sensors.h"
#include "pico/rand.h"

static constexpr int WINDOW = 64;  // cửa sổ nhớ các seq gần nhất để phát hiện trùng

struct SourceState {
    bool active;
    uint32_t boot_id;
    uint32_t first_seq, highest;
    uint64_t seen;  // bit i = đã nhận seq (highest - i)
    uint32_t unique, dup, late, retry_rx, stats_rx;
    uint8_t last_parent;
    uint8_t last_hop;
};

static SourceState r_src[MAX_NODE_ID + 1];
static uint32_t r_local_seq = 0, r_ack_fail = 0, r_ack_test_drop = 0;
static uint8_t r_ack_drop_pct = 0;  // test E4
static btstack_timer_source_t r_timer;
static uint32_t r_next_local = 0, r_next_stats = 0;

static const char *classify(SourceState &s, const DataPacket &d) {
    if (!s.active || d.boot_id != s.boot_id) {
        if (s.active) {
            LOGJ("NEW_SESSION", "\"node\":\"%c\",\"old_boot\":%" PRIu32 ",\"new_boot\":%" PRIu32,
                 node_name(d.source_id), s.boot_id, d.boot_id);
        }
        memset(&s, 0, sizeof(s));
        s.active = true;
        s.boot_id = d.boot_id;
        s.first_seq = s.highest = d.seq;
        s.seen = 1;
        s.last_parent = 0xFF;
        return "FIRST";
    }
    if (d.seq > s.highest) {
        uint32_t shift = d.seq - s.highest;
        s.seen = shift >= WINDOW ? 0 : (s.seen << shift);
        s.seen |= 1;
        const char *v = (shift == 1) ? "OK" : "GAP";
        s.highest = d.seq;
        return v;
    }
    uint32_t back = s.highest - d.seq;
    if (back >= WINDOW) return "DUP";  // quá cũ, coi như đã xử lý
    uint64_t bit = 1ull << back;
    if (s.seen & bit) return "DUP";
    s.seen |= bit;
    if (d.seq < s.first_seq) s.first_seq = d.seq;
    return "LATE";
}

static void on_data(uint8_t from_child, const DataPacket &d) {
    if (d.source_id == ROOT_ID || d.source_id > MAX_NODE_ID) {
        LOGJ("RX_BAD", "\"via\":\"%c\",\"src\":%u", node_name(from_child), d.source_id);
        return;
    }
    SourceState &s = r_src[d.source_id];
    const char *check = classify(s, d);
    bool dup = check[0] == 'D';
    if (!dup) s.unique++;
    else s.dup++;
    if (check[0] == 'L') s.late++;
    if (d.flags & FLAG_RETRY) s.retry_rx++;
    if (d.parent_id != s.last_parent && d.parent_id != 0xFF) {
        if (s.last_parent != 0xFF) {
            LOGJ("ROUTE_CHANGE", "\"node\":\"%c\",\"from\":\"%c\",\"to\":\"%c\",\"seq\":%" PRIu32,
                 node_name(d.source_id), node_name(s.last_parent), node_name(d.parent_id), d.seq);
        }
        s.last_parent = d.parent_id;
    }
    s.last_hop = d.hop;

    AckRootPacket ack{make_hdr(MSG_ACK_ROOT), d.source_id, 0, d.boot_id, d.seq};
    int ack_ok;  // 1 = đã xếp gửi, 0 = lỗi (con không còn), -1 = test E4 cố ý bỏ
    if (r_ack_drop_pct && get_rand_32() % 100 < r_ack_drop_pct) {
        ack_ok = -1;
        r_ack_test_drop++;
    } else {
        ack_ok = downlink_send(from_child, (const uint8_t *)&ack, sizeof(ack)) ? 1 : 0;
        if (!ack_ok) r_ack_fail++;
    }

    LOGJ("DATA_RX",
         "\"node\":\"%c\",\"boot\":%" PRIu32 ",\"seq\":%" PRIu32 ",\"hop\":%u,\"ttl\":%u,\"flags\":%u,"
         "\"parent\":\"%c\",\"via\":\"%c\",\"ldr\":%u,\"i_ma_x10\":%d,\"vbat_mv\":%u,\"check\":\"%s\",\"ack\":%d",
         node_name(d.source_id), d.boot_id, d.seq, d.hop, d.ttl, d.flags, node_name(d.parent_id),
         node_name(from_child), d.ldr, d.current_ma_x10, d.vbat_mv, check, ack_ok);
}

static void on_stats(uint8_t from_child, const StatsPacket &st) {
    if (st.source_id <= MAX_NODE_ID) r_src[st.source_id].stats_rx++;
    LOGJ("STATS_RX",
         "\"node\":\"%c\",\"via\":\"%c\",\"boot\":%" PRIu32 ",\"gen\":%" PRIu32 ",\"retries\":%u,\"qfull\":%u,"
         "\"parent_lost\":%u,\"rssi\":%d,\"rtt_avg_ms\":%u,\"i_avg_x10\":%d",
         node_name(st.source_id), node_name(from_child), st.boot_id, st.generated, st.retries, st.queue_full,
         st.parent_lost, st.rssi_dbm, st.rtt_avg_ms, st.current_avg_x10);
}

void root_on_frame(uint8_t from_child, const uint8_t *frame, uint16_t len) {
    uint8_t type = hdr_type(frame[0]);
    if (type == MSG_DATA && len == sizeof(DataPacket)) {
        DataPacket d;
        memcpy(&d, frame, sizeof(d));
        on_data(from_child, d);
    } else if (type == MSG_STATS && len == sizeof(StatsPacket)) {
        StatsPacket st;
        memcpy(&st, frame, sizeof(st));
        on_stats(from_child, st);
    } else {
        LOGJ("RX_BAD", "\"via\":\"%c\",\"msg\":%u,\"len\":%u", node_name(from_child), type, len);
    }
}

void root_on_child_connected(uint8_t) {}

void root_set_ack_drop(uint8_t percent) {
    r_ack_drop_pct = percent > 100 ? 100 : percent;
    LOGJ("CONFIG", "\"ack_drop_pct\":%u", r_ack_drop_pct);
}

static void root_stats() {
    for (uint8_t id = 1; id <= MAX_NODE_ID; id++) {
        SourceState &s = r_src[id];
        if (!s.active) continue;
        uint32_t span = s.highest - s.first_seq + 1;  // số gói lẽ ra phải tới (theo seq)
        uint32_t missing = span > s.unique ? span - s.unique : 0;
        LOGJ("ROOT_STATS",
             "\"node\":\"%c\",\"boot\":%" PRIu32 ",\"first_seq\":%" PRIu32 ",\"highest\":%" PRIu32
             ",\"unique\":%" PRIu32 ",\"missing\":%" PRIu32 ",\"dup\":%" PRIu32 ",\"late\":%" PRIu32
             ",\"retry_rx\":%" PRIu32 ",\"stats_rx\":%" PRIu32 ",\"rssi\":%d,\"parent\":\"%c\",\"hop\":%u",
             node_name(id), s.boot_id, s.first_seq, s.highest, s.unique, missing, s.dup, s.late, s.retry_rx,
             s.stats_rx, downlink_rssi(id), node_name(s.last_parent), s.last_hop);
    }
    LOGJ("ROOT_SUMMARY", "\"children\":%d,\"ack_fail\":%" PRIu32 ",\"ack_test_drop\":%" PRIu32
         ",\"ack_drop_pct\":%u,\"boot\":%" PRIu32 ",\"fw\":\"%s\"",
         downlink_ready_count(), r_ack_fail, r_ack_test_drop, r_ack_drop_pct, g_boot_id, WSN_GIT);
}

static void root_timer(btstack_timer_source_t *ts) {
    uint32_t now = now_ms();
    if ((int32_t)(now - r_next_local) >= 0) {
        // Dữ liệu cục bộ của Root (Root không có cảm biến): gắn cờ FAKE, gateway tách riêng.
        r_next_local += g_cfg.pw.data_period_ms;
        SensorSample s = sensors_read(r_local_seq);
        LOGJ("LOCAL_DATA", "\"node\":\"R\",\"seq\":%" PRIu32 ",\"ldr\":%u,\"flags\":%u", r_local_seq++, s.ldr,
             s.flags);
    }
    if ((int32_t)(now - r_next_stats) >= 0) {
        r_next_stats += g_cfg.pw.stats_period_ms;
        downlink_tick();
        root_stats();
    }
    btstack_run_loop_set_timer(ts, 100);
    btstack_run_loop_add_timer(ts);
}

void root_start() {
    uint32_t now = now_ms();
    r_next_local = now + g_cfg.pw.data_period_ms;
    r_next_stats = now + g_cfg.pw.stats_period_ms;
    btstack_run_loop_set_timer(&r_timer, 100);
    btstack_run_loop_set_timer_handler(&r_timer, root_timer);
    btstack_run_loop_add_timer(&r_timer);
}
