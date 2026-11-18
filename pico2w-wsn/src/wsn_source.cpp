// wsn_source.cpp — dữ liệu của chính node: tạo DATA định kỳ, chờ ACK_ROOT, gửi lại, gửi STATS.
//
// Mỗi gói DATA tạo ra được giữ trong bảng "pending" tới khi Root xác nhận (ACK_ROOT).
// Quá timeout (theo số hop) thì gửi lại với cùng danh tính (source_id, boot_id, seq) + cờ RETRY.
// Quá max_tries lần thì bỏ và đếm. Gói vẫn được tạo khi đang mất cha (để PDR phản ánh đúng
// thời gian mất kết nối); chúng nằm trong pending và được gửi khi có cha trở lại.
#include <string.h>

#include "wsn_config.h"
#include "wsn_net.h"
#include "wsn_sensors.h"

static constexpr int PENDING_LEN = 16;
static constexpr uint32_t HOUSEKEEP_MS = 100;

struct Pending {
    bool used;
    uint8_t tries;     // số lần đã đưa vào hàng đợi gửi
    uint32_t sent_at;  // lần gửi gần nhất
    DataPacket pkt;
};

static Pending s_pend[PENDING_LEN];
static uint32_t s_seq = 0;
static uint32_t s_generated = 0, s_acked = 0, s_dropped = 0, s_late_acks = 0;
static uint16_t s_retries = 0;
static uint32_t s_rtt_sum = 0, s_rtt_n = 0;      // trong chu kỳ STATS hiện tại
static int32_t s_cur_sum = 0;                     // dòng (0.1 mA) trong chu kỳ STATS hiện tại
static uint32_t s_cur_n = 0;
static uint32_t s_next_data = 0, s_next_stats = 0, s_next_sample = 0;
static btstack_timer_source_t s_timer;

static uint32_t ack_timeout_ms() { return g_cfg.pw.ack_timeout_per_hop_ms * (g_cfg.depth ? g_cfg.depth : 1); }

static void send_pending(Pending &p, uint32_t now) {
    if (p.tries > 0) p.pkt.flags |= FLAG_RETRY;
    p.pkt.parent_id = uplink_parent_id();
    if (uplink_enqueue((const uint8_t *)&p.pkt, sizeof(p.pkt))) {
        if (p.tries > 0) {
            if (s_retries < 0xFFFF) s_retries++;
            LOGJ("RETRY", "\"seq\":%" PRIu32 ",\"try\":%u", p.pkt.seq, p.tries + 1);
        }
        p.tries++;
        p.sent_at = now;
    }
}

static void generate_data(uint32_t now) {
    SensorSample s = sensors_read(s_seq);
    // Bảng pending đầy (mất cha lâu): bỏ gói cũ nhất
    Pending *slot = nullptr;
    Pending *oldest = nullptr;
    for (auto &p : s_pend) {
        if (!p.used) {
            slot = &p;
            break;
        }
        if (!oldest || p.pkt.seq < oldest->pkt.seq) oldest = &p;
    }
    if (!slot) {
        s_dropped++;
        LOGJ("DROP", "\"seq\":%" PRIu32 ",\"why\":\"pending_full\"", oldest->pkt.seq);
        slot = oldest;
    }
    DataPacket &d = slot->pkt;
    d.hdr = make_hdr(MSG_DATA);
    d.source_id = g_cfg.id;
    d.ttl = DEFAULT_TTL;
    d.hop = 0;
    d.flags = s.flags | (g_cfg.pw.low_power ? FLAG_LOW_POWER : 0);
    d.parent_id = uplink_parent_id();
    d.boot_id = g_boot_id;
    d.seq = s_seq++;
    d.ldr = s.ldr;
    d.current_ma_x10 = s.current_ma_x10;
    d.vbat_mv = s.vbat_mv;
    slot->used = true;
    slot->tries = 0;
    slot->sent_at = 0;
    s_generated++;
    LOGJ("DATA_TX", "\"seq\":%" PRIu32 ",\"ldr\":%u,\"i_ma_x10\":%d,\"vbat_mv\":%u,\"flags\":%u,\"up\":%d",
         d.seq, d.ldr, d.current_ma_x10, d.vbat_mv, d.flags, uplink_ready() ? 1 : 0);
    if (uplink_ready()) send_pending(*slot, now);
}

static void send_stats() {
    StatsPacket st{};
    st.hdr = make_hdr(MSG_STATS);
    st.source_id = g_cfg.id;
    st.rssi_dbm = uplink_rssi();
    st.parent_lost = uplink_parent_lost_count();
    st.boot_id = g_boot_id;
    st.generated = s_generated;
    st.retries = s_retries;
    st.queue_full = uplink_queue_full_count();
    uint32_t rtt = s_rtt_n ? s_rtt_sum / s_rtt_n : 0;
    st.rtt_avg_ms = (uint16_t)(rtt > 0xFFFF ? 0xFFFF : rtt);
    st.current_avg_x10 = s_cur_n ? (int16_t)(s_cur_sum / (int32_t)s_cur_n) : INT16_MIN;
    LOGJ("NODE_STATS", "\"gen\":%" PRIu32 ",\"acked\":%" PRIu32 ",\"retries\":%u,\"dropped\":%" PRIu32
         ",\"late_acks\":%" PRIu32 ",\"qfull\":%u,\"parent_lost\":%u,\"rssi\":%d,\"rtt_avg_ms\":%u,\"i_avg_x10\":%d,"
         "\"parent\":\"%c\",\"up\":%d",
         s_generated, s_acked, s_retries, s_dropped, s_late_acks, st.queue_full, st.parent_lost, st.rssi_dbm,
         st.rtt_avg_ms, st.current_avg_x10, node_name(uplink_parent_id()), uplink_ready() ? 1 : 0);
    s_rtt_sum = s_rtt_n = 0;
    s_cur_sum = 0;
    s_cur_n = 0;
    if (uplink_ready()) uplink_enqueue((const uint8_t *)&st, sizeof(st));  // STATS không cần ACK
}

static void housekeeping(btstack_timer_source_t *ts) {
    uint32_t now = now_ms();
    if ((int32_t)(now - s_next_sample) >= 0) {  // lấy mẫu dòng mỗi 1 s cho dòng trung bình
        s_next_sample += 1000;
        if (sensors_has_ina219()) {
            SensorSample s = sensors_read(0);
            s_cur_sum += s.current_ma_x10;
            s_cur_n++;
        }
    }
    if ((int32_t)(now - s_next_data) >= 0) {
        s_next_data += g_cfg.pw.data_period_ms;
        generate_data(now);
    }
    if ((int32_t)(now - s_next_stats) >= 0) {
        s_next_stats += g_cfg.pw.stats_period_ms;
        uplink_tick();
        sensors_probe();
        if (cfg_has_children()) downlink_tick();  // relay: RSSI các con + RELAY_STATS
        send_stats();
    }
    // Gửi lại gói quá timeout, hoặc gói chưa gửi lần nào (tạo ra lúc mất cha)
    if (uplink_ready()) {
        uint32_t to = ack_timeout_ms();
        for (auto &p : s_pend) {
            if (!p.used) continue;
            if (p.tries > 0 && now - p.sent_at < to) continue;
            if (p.tries >= g_cfg.pw.max_tries) {
                p.used = false;
                s_dropped++;
                LOGJ("DROP", "\"seq\":%" PRIu32 ",\"why\":\"max_tries\"", p.pkt.seq);
                continue;
            }
            send_pending(p, now);
        }
    }
    btstack_run_loop_set_timer(ts, HOUSEKEEP_MS);
    btstack_run_loop_add_timer(ts);
}

void source_start() {
    uint32_t now = now_ms();
    s_next_data = now + g_cfg.pw.data_period_ms;
    s_next_stats = now + g_cfg.pw.stats_period_ms;
    s_next_sample = now + 1000;
    btstack_run_loop_set_timer(&s_timer, HOUSEKEEP_MS);
    btstack_run_loop_set_timer_handler(&s_timer, housekeeping);
    btstack_run_loop_add_timer(&s_timer);
}

void source_on_ack(const AckRootPacket *ack) {
    if (ack->boot_id != g_boot_id) return;
    for (auto &p : s_pend) {
        if (p.used && p.pkt.seq == ack->seq) {
            uint32_t rtt = now_ms() - p.sent_at;
            p.used = false;
            s_acked++;
            s_rtt_sum += rtt;
            s_rtt_n++;
            LOGJ("ACK_RX", "\"seq\":%" PRIu32 ",\"rtt_ms\":%" PRIu32 ",\"tries\":%u", ack->seq, rtt, p.tries);
            return;
        }
    }
    s_late_acks++;  // ACK cho gói đã được xác nhận trước đó (do gửi lại) hoặc đã bỏ
}

void source_set_period(uint32_t ms) {
    if (ms < 20) ms = 20;
    LOGJ("CONFIG", "\"data_period_ms\":%" PRIu32 ",\"prev\":%" PRIu32, ms, g_cfg.pw.data_period_ms);
    g_cfg.pw.data_period_ms = ms;
    s_next_data = now_ms() + ms;
}

void source_on_parent_change() {
    // Có cha mới: gói chưa có ACK gửi lại ngay ở lần housekeeping tới (không chờ hết timeout)
    // Bỏ qua gói vừa gửi < 500 ms trước: chắc chắn đã đi trên liên kết mới (liên kết cũ chỉ bị phát hiện
    // mất sau supervision timeout 4 s, thiết lập lại mất ~1 s), gửi lại ngay chỉ phí một lượt thử.
    uint32_t now = now_ms();
    for (auto &p : s_pend)
        if (p.used && p.tries > 0 && now - p.sent_at >= 500) p.sent_at = now - ack_timeout_ms();
}
