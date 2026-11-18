// wsn_downlink.cpp — phía node cha của liên kết: Central + GATT Client, nối tới các node con.
//
// Quét quảng bá, chỉ kết nối tới con có node_id được phép (topology). Sau khi kết nối:
// tìm service -> tìm 2 characteristic -> bật notify trên DATA -> gửi HELLO (node_id của cha).
// Gói từ con: ở Root thì đưa cho wsn_root; ở relay thì chuyển tiếp lên cha (giảm TTL, tăng hop).
// Gói xuống con (ACK_ROOT, HELLO) đi bằng write-without-response qua hàng đợi riêng của mỗi con.
#include <string.h>

#include "wsn_config.h"
#include "wsn_net.h"

static const uint8_t SERVICE_UUID[16] = {0xA7, 0xE5, 0x00, 0x00, 0x3C, 0x1D, 0x4B, 0x8E,
                                         0x9F, 0x21, 0x7D, 0x0C, 0x5E, 0x2B, 0x9A, 0x10};
static const uint8_t DATA_UUID[16] = {0xA7, 0xE5, 0x00, 0x01, 0x3C, 0x1D, 0x4B, 0x8E,
                                      0x9F, 0x21, 0x7D, 0x0C, 0x5E, 0x2B, 0x9A, 0x10};
static const uint8_t ACK_UUID[16] = {0xA7, 0xE5, 0x00, 0x02, 0x3C, 0x1D, 0x4B, 0x8E,
                                     0x9F, 0x21, 0x7D, 0x0C, 0x5E, 0x2B, 0x9A, 0x10};

static constexpr uint32_t CONNECT_TIMEOUT_MS = 5000;
static constexpr int MAX_CHILDREN = 3;
static constexpr int DOWN_QUEUE_LEN = 32;  // đủ cho chùm ACK khi relay nối lại và đổ hàng đợi lên
// MESH: relay chỉ nhận một node "mồ côi" làm con khi đã thấy nó quảng bá liên tục chừng này mà Root vẫn
// chưa nhận -> ưu tiên nối thẳng Root, chỉ đi vòng khi Root không nghe thấy node đó.
static constexpr uint32_t MESH_ADOPT_DELAY_MS = 1500;
static constexpr uint32_t MESH_SEEN_GAP_MS = 3000;  // không thấy quảng bá quá lâu (đã có cha) -> đếm lại từ đầu
// (relay vừa giữ liên kết vừa quét nên bắt được quảng bá thưa; 600 ms làm bộ đếm reset mãi, không bao giờ nhận)

enum ChildState : uint8_t { CH_FREE, CH_FIND_SERVICE, CH_FIND_CHARS, CH_SUBSCRIBE, CH_READY };

struct DownFrame {
    uint8_t len;
    uint8_t b[MAX_FRAME];
};

struct Child {
    ChildState state;
    hci_con_handle_t con;
    bd_addr_t addr;
    uint8_t id;
    uint32_t connected_at;
    gatt_client_service_t service;
    bool have_service, have_data, have_ack, listening;
    gatt_client_characteristic_t data_char, ack_char;
    gatt_client_notification_t listener;
    DownFrame q[DOWN_QUEUE_LEN];
    int q_head, q_count;
    bool write_requested;
    btstack_context_callback_registration_t write_req;
    int8_t rssi;
};

static Child d_child[MAX_CHILDREN];
static bool d_connecting = false;
static uint8_t d_connecting_id = 0xFF;
static btstack_timer_source_t d_connect_timer;
static bool d_scanning = false;

// Relay: bảng "source_id -> con đã đưa gói của source đó lên" để ACK đi ngược đúng đường.
static uint8_t d_route[MAX_NODE_ID + 1];
static uint32_t d_relay_fwd = 0, d_relay_ttl_drop = 0, d_relay_dup = 0, d_relay_qfull = 0;
static uint8_t d_deny_mask = 0;  // Root (test): coi như không nghe thấy các node này (giả lập ở quá xa)
static uint32_t d_first_seen[MAX_NODE_ID + 1], d_last_seen[MAX_NODE_ID + 1];  // MESH: theo dõi quảng bá

static Child *child_by_con(hci_con_handle_t con) {
    for (auto &c : d_child)
        if (c.state != CH_FREE && c.con == con) return &c;
    return nullptr;
}

static Child *child_by_id(uint8_t id) {
    for (auto &c : d_child)
        if (c.state != CH_FREE && c.id == id) return &c;
    return nullptr;
}

static Child *child_alloc() {
    for (auto &c : d_child)
        if (c.state == CH_FREE) return &c;
    return nullptr;
}

// Có nhận node id làm con lúc này không? Relay chưa có cha thì không nhận con có cha dự phòng
// (DIAMOND): để con đó nối tới cha khác đang có đường lên Root, thay vì nằm chờ ở đây.
static bool child_allowed(uint8_t id) {
    if (!(g_cfg.child_mask & (1u << id))) return false;
    if (d_deny_mask & (1u << id)) return false;
    if (g_cfg.path_mask & (1u << id)) return false;  // MESH: không nhận node đang ở phía trên mình (vòng lặp)
    if (cfg_is_root() || !(g_cfg.child_alt_mask & (1u << id))) return true;
    return uplink_ready();
}

// Còn con được phép nào chưa kết nối không?
static bool want_more_children() {
    for (uint8_t id = 0; id <= MAX_NODE_ID; id++)
        if (child_allowed(id) && !child_by_id(id)) return true;
    return false;
}

static void update_scan() {
    bool want = !d_connecting && child_alloc() != nullptr && want_more_children();
    if (want && !d_scanning) {
        // Quét thụ động. Root và topology cố định: liên tục (30 ms / 30 ms). Relay ở MESH gần như lúc nào cũng
        // "còn con chưa nối" nên quét 30 ms mỗi 100 ms để chừa thời gian radio cho các liên kết đang có.
        uint16_t itv = (g_cfg.mesh && !cfg_is_root()) ? 0x0060 : 0x0030;  // relay MESH: 30 ms mỗi 60 ms
        gap_set_scan_params(0, itv, 0x0030, 0);
        gap_start_scan();
        d_scanning = true;
        if (g_cfg.mesh) LOGJ("SCAN", "\"on\":1");
    } else if (!want && d_scanning) {
        gap_stop_scan();
        d_scanning = false;
        if (g_cfg.mesh) LOGJ("SCAN", "\"on\":0");
    }
}

void downlink_start() {
    for (auto &r : d_route) r = 0xFF;
    const PowerParams &p = g_cfg.pw;
    // Tham số kết nối do Central (cha) quyết định: CI, peripheral latency, supervision timeout.
    gap_set_connection_parameters(0x0060, 0x0030, p.conn_interval, p.conn_interval, p.conn_latency,
                                  p.supervision_10ms, 0, 0);
    LOGJ("SCAN_START", "\"children_mask\":%u,\"ci_ms\":%u,\"latency\":%u", g_cfg.child_mask,
         (unsigned)(p.conn_interval * 125 / 100), p.conn_latency);
    update_scan();
}

// Lấy node_id từ manufacturer data (company 0xFFFF) nếu gói quảng bá có service WSN.
static int adv_node_id(const uint8_t *data, uint8_t len) {
    uint8_t le_uuid[16];
    reverse_128(SERVICE_UUID, le_uuid);
    bool has_service = false;
    int id = -1;
    ad_context_t ctx;
    for (ad_iterator_init(&ctx, len, data); ad_iterator_has_more(&ctx); ad_iterator_next(&ctx)) {
        uint8_t type = ad_iterator_get_data_type(&ctx);
        uint8_t dlen = ad_iterator_get_data_len(&ctx);
        const uint8_t *d = ad_iterator_get_data(&ctx);
        if (type == BLUETOOTH_DATA_TYPE_COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS && dlen == 16 &&
            memcmp(d, le_uuid, 16) == 0)
            has_service = true;
        if (type == BLUETOOTH_DATA_TYPE_MANUFACTURER_SPECIFIC_DATA && dlen == 3 && d[0] == 0xFF &&
            d[1] == 0xFF)
            id = d[2];
    }
    return has_service ? id : -1;
}

static void connect_timeout(btstack_timer_source_t *) {
    if (!d_connecting) return;
    LOGJ("CONNECT_TIMEOUT", "\"node\":\"%c\"", node_name(d_connecting_id));
    gap_connect_cancel();  // sự kiện connection complete (status != 0) sẽ quét lại
}

void downlink_on_adv(uint8_t *packet) {
    if (d_connecting || !child_alloc()) return;
    int id = adv_node_id(gap_event_advertising_report_get_data(packet),
                         gap_event_advertising_report_get_data_length(packet));
    if (id < 0 || id > MAX_NODE_ID || !child_allowed((uint8_t)id) || child_by_id((uint8_t)id)) return;
    if (g_cfg.mesh && !cfg_is_root()) {
        uint32_t now = now_ms();
        if (d_first_seen[id] == 0 || now - d_last_seen[id] > MESH_SEEN_GAP_MS) {
            d_first_seen[id] = now;
            LOGJ("ORPHAN_SEEN", "\"node\":\"%c\",\"rssi_dbm\":%d", node_name((uint8_t)id),
                 (int8_t)gap_event_advertising_report_get_rssi(packet));
        }
        d_last_seen[id] = now;
        if (now - d_first_seen[id] < MESH_ADOPT_DELAY_MS) return;  // để Root có cơ hội nhận trước
    }
    bd_addr_t addr;
    gap_event_advertising_report_get_address(packet, addr);
    bd_addr_type_t type = (bd_addr_type_t)gap_event_advertising_report_get_address_type(packet);
    LOGJ("FOUND", "\"node\":\"%c\",\"peer\":\"%s\",\"rssi_dbm\":%d", node_name((uint8_t)id),
         bd_addr_to_str(addr), (int8_t)gap_event_advertising_report_get_rssi(packet));
    gap_stop_scan();
    d_scanning = false;
    d_connecting = true;
    d_connecting_id = (uint8_t)id;
    gap_connect(addr, type);
    btstack_run_loop_set_timer(&d_connect_timer, CONNECT_TIMEOUT_MS);
    btstack_run_loop_set_timer_handler(&d_connect_timer, connect_timeout);
    btstack_run_loop_add_timer(&d_connect_timer);
}

// ---------------------------------------------------------------- gửi xuống con

static void flush_down(Child &c);

// BTstack gọi khi kênh ATT lại nhận được write-without-response.
static void on_can_write(void *context) {
    Child &c = *static_cast<Child *>(context);
    c.write_requested = false;
    if (c.state == CH_READY) flush_down(c);
}

static void flush_down(Child &c) {
    while (c.q_count > 0) {
        DownFrame &f = c.q[c.q_head];
        uint8_t status = gatt_client_write_value_of_characteristic_without_response(
            c.con, c.ack_char.value_handle, f.len, f.b);
        if (status == GATT_CLIENT_BUSY || status == BTSTACK_ACL_BUFFERS_FULL) {
            if (!c.write_requested) {
                c.write_requested = true;
                c.write_req.callback = on_can_write;
                c.write_req.context = &c;
                gatt_client_request_to_write_without_response(&c.write_req, c.con);
            }
            return;
        }
        if (status != ERROR_CODE_SUCCESS)
            LOGJ("DOWN_TX_FAIL", "\"node\":\"%c\",\"status\":%u", node_name(c.id), status);
        c.q_head = (c.q_head + 1) % DOWN_QUEUE_LEN;
        c.q_count--;
    }
}

bool downlink_send(uint8_t child_id, const uint8_t *frame, uint16_t len) {
    Child *c = child_by_id(child_id);
    if (!c || c->state != CH_READY) return false;
    // Khung y hệt còn chờ trong hàng đợi (vd ACK cho gói DUP ngay sau ACK cho gói LATE) thì không thêm
    for (int i = 0; i < c->q_count; i++) {
        const DownFrame &q = c->q[(c->q_head + i) % DOWN_QUEUE_LEN];
        if (q.len == len && memcmp(q.b, frame, len) == 0) return true;
    }
    if (c->q_count >= DOWN_QUEUE_LEN) {
        // Bỏ gói cũ nhất: ACK mới quan trọng hơn (gói cũ có thể đã quá timeout ở node nguồn)
        c->q_head = (c->q_head + 1) % DOWN_QUEUE_LEN;
        c->q_count--;
        LOGJ("DOWN_QUEUE_FULL", "\"node\":\"%c\"", node_name(child_id));
    }
    DownFrame &f = c->q[(c->q_head + c->q_count) % DOWN_QUEUE_LEN];
    f.len = (uint8_t)len;
    memcpy(f.b, frame, len);
    c->q_count++;
    if (!c->write_requested) flush_down(*c);
    return true;
}

void downlink_route_ack(const AckRootPacket *ack) {
    uint8_t via = ack->source_id <= MAX_NODE_ID ? d_route[ack->source_id] : 0xFF;
    if (via == 0xFF || !downlink_send(via, (const uint8_t *)ack, sizeof(*ack))) {
        LOGJ("ACK_NO_ROUTE", "\"src\":\"%c\",\"seq\":%" PRIu32, node_name(ack->source_id), ack->seq);
    }
}

// ---------------------------------------------------------------- relay (chuyển tiếp lên cha)

static void relay_on_frame(Child &c, const uint8_t *frame, uint16_t len) {
    uint8_t type = hdr_type(frame[0]);
    if (type == MSG_DATA && len == sizeof(DataPacket)) {
        DataPacket d;
        memcpy(&d, frame, sizeof(d));
        if (d.source_id <= MAX_NODE_ID) d_route[d.source_id] = c.id;  // học đường đi ngược cho ACK
        if (d.ttl <= 1) {
            d_relay_ttl_drop++;
            LOGJ("TTL_DROP", "\"src\":\"%c\",\"seq\":%" PRIu32, node_name(d.source_id), d.seq);
            return;
        }
        // Lọc trùng: gói cùng danh tính còn nằm trong hàng đợi chưa gửi thì bỏ bản mới.
        if (uplink_queued(d.source_id, d.boot_id, d.seq)) {
            d_relay_dup++;
            LOGJ("RELAY_DUP", "\"src\":\"%c\",\"seq\":%" PRIu32, node_name(d.source_id), d.seq);
            return;
        }
        d.ttl--;
        d.hop++;
        if (uplink_enqueue((const uint8_t *)&d, sizeof(d))) {
            d_relay_fwd++;
        } else {
            d_relay_qfull++;
            LOGJ("QUEUE_FULL", "\"src\":\"%c\",\"seq\":%" PRIu32, node_name(d.source_id), d.seq);
        }
    } else if (type == MSG_STATS && len == sizeof(StatsPacket)) {
        StatsPacket s;
        memcpy(&s, frame, sizeof(s));
        if (s.source_id <= MAX_NODE_ID) d_route[s.source_id] = c.id;
        if (!uplink_enqueue(frame, len)) d_relay_qfull++;
    } else {
        LOGJ("RX_BAD", "\"link\":\"child\",\"node\":\"%c\",\"len\":%u", node_name(c.id), len);
    }
}

// ---------------------------------------------------------------- GATT client

static void gatt_handler(uint8_t packet_type, uint16_t, uint8_t *packet, uint16_t) {
    if (packet_type != HCI_EVENT_PACKET) return;
    switch (hci_event_packet_get_type(packet)) {
    case GATT_EVENT_SERVICE_QUERY_RESULT: {
        Child *c = child_by_con(gatt_event_service_query_result_get_handle(packet));
        if (!c) break;
        gatt_event_service_query_result_get_service(packet, &c->service);
        c->have_service = true;
        break;
    }
    case GATT_EVENT_CHARACTERISTIC_QUERY_RESULT: {
        Child *c = child_by_con(gatt_event_characteristic_query_result_get_handle(packet));
        if (!c) break;
        gatt_client_characteristic_t ch;
        gatt_event_characteristic_query_result_get_characteristic(packet, &ch);
        if (memcmp(ch.uuid128, DATA_UUID, 16) == 0) {
            c->data_char = ch;
            c->have_data = true;
        } else if (memcmp(ch.uuid128, ACK_UUID, 16) == 0) {
            c->ack_char = ch;
            c->have_ack = true;
        }
        break;
    }
    case GATT_EVENT_QUERY_COMPLETE: {
        Child *c = child_by_con(gatt_event_query_complete_get_handle(packet));
        if (!c) break;
        uint8_t att_status = gatt_event_query_complete_get_att_status(packet);
        if (att_status != ATT_ERROR_SUCCESS) {
            LOGJ("GATT_ERROR", "\"node\":\"%c\",\"step\":%u,\"att_status\":%u", node_name(c->id), c->state,
                 att_status);
            gap_disconnect(c->con);
            break;
        }
        if (c->state == CH_FIND_SERVICE) {
            if (!c->have_service) {
                LOGJ("GATT_ERROR", "\"node\":\"%c\",\"msg\":\"service not found\"", node_name(c->id));
                gap_disconnect(c->con);
                break;
            }
            c->state = CH_FIND_CHARS;
            gatt_client_discover_characteristics_for_service(gatt_handler, c->con, &c->service);
        } else if (c->state == CH_FIND_CHARS) {
            if (!c->have_data || !c->have_ack) {
                LOGJ("GATT_ERROR", "\"node\":\"%c\",\"msg\":\"characteristics not found\"", node_name(c->id));
                gap_disconnect(c->con);
                break;
            }
            c->state = CH_SUBSCRIBE;
            // Đăng ký nhận notify của characteristic DATA, rồi ghi CCCD để con bắt đầu gửi
            gatt_client_listen_for_characteristic_value_updates(&c->listener, gatt_handler, c->con,
                                                                &c->data_char);
            c->listening = true;
            gatt_client_write_client_characteristic_configuration(
                gatt_handler, c->con, &c->data_char, GATT_CLIENT_CHARACTERISTICS_CONFIGURATION_NOTIFICATION);
        } else if (c->state == CH_SUBSCRIBE) {
            c->state = CH_READY;
            LOGJ("CHILD_READY", "\"node\":\"%c\",\"peer\":\"%s\",\"setup_ms\":%" PRIu32, node_name(c->id),
                 bd_addr_to_str(c->addr), now_ms() - c->connected_at);
            HelloPacket h{make_hdr(MSG_HELLO), g_cfg.id, (uint8_t)(g_cfg.path_mask | (1u << g_cfg.id))};
            downlink_send(c->id, (const uint8_t *)&h, sizeof(h));
            if (cfg_is_root()) root_on_child_connected(c->id);
        }
        break;
    }
    case GATT_EVENT_NOTIFICATION: {
        Child *c = child_by_con(gatt_event_notification_get_handle(packet));
        if (!c || c->state != CH_READY) break;
        const uint8_t *v = gatt_event_notification_get_value(packet);
        uint16_t len = gatt_event_notification_get_value_length(packet);
        if (len < 1 || hdr_version(v[0]) != PROTO_VERSION) {
            LOGJ("RX_BAD", "\"link\":\"child\",\"node\":\"%c\",\"len\":%u", node_name(c->id), len);
            break;
        }
        if (cfg_is_root()) {
            root_on_frame(c->id, v, len);
        } else {
            relay_on_frame(*c, v, len);
        }
        break;
    }
    default:
        break;
    }
}

// ---------------------------------------------------------------- sự kiện HCI

void downlink_on_connection_complete(uint8_t *packet) {
    bool was_connecting = d_connecting;
    d_connecting = false;
    btstack_run_loop_remove_timer(&d_connect_timer);
    uint8_t status = gap_subevent_le_connection_complete_get_status(packet);
    if (status != ERROR_CODE_SUCCESS) {
        LOGJ("CONNECT_FAIL", "\"node\":\"%c\",\"status\":\"0x%02x\"", node_name(d_connecting_id), status);
        update_scan();
        return;
    }
    hci_con_handle_t con = gap_subevent_le_connection_complete_get_connection_handle(packet);
    Child *c = child_alloc();
    if (!was_connecting || !c) {
        gap_disconnect(con);
        update_scan();
        return;
    }
    memset(c, 0, sizeof(*c));
    c->state = CH_FIND_SERVICE;
    c->con = con;
    c->id = d_connecting_id;
    c->connected_at = now_ms();
    gap_subevent_le_connection_complete_get_peer_address(packet, c->addr);
    uint16_t itv = gap_subevent_le_connection_complete_get_conn_interval(packet);
    LOGJ("CONNECTED", "\"link\":\"child\",\"node\":\"%c\",\"peer\":\"%s\",\"interval_ms\":%u.%02u,\"latency\":%u",
         node_name(c->id), bd_addr_to_str(c->addr), itv * 125 / 100, (itv * 125) % 100,
         gap_subevent_le_connection_complete_get_conn_latency(packet));
    gatt_client_discover_primary_services_by_uuid128(gatt_handler, con, SERVICE_UUID);
    update_scan();
}

bool downlink_on_disconnected(hci_con_handle_t con, uint8_t reason) {
    Child *c = child_by_con(con);
    if (!c) return false;
    LOGJ("DISCONNECTED", "\"link\":\"child\",\"node\":\"%c\",\"reason\":\"0x%02x\",\"up_ms\":%" PRIu32,
         node_name(c->id), reason, now_ms() - c->connected_at);
    if (c->listening) gatt_client_stop_listening_for_characteristic_value_updates(&c->listener);
    c->state = CH_FREE;
    update_scan();
    return true;
}

void downlink_on_rssi(hci_con_handle_t con, int8_t rssi) {
    Child *c = child_by_con(con);
    if (c) c->rssi = rssi;
}

int8_t downlink_rssi(uint8_t child_id) {
    Child *c = child_by_id(child_id);
    return c ? c->rssi : 0;
}

void downlink_on_uplink(bool up) {
    if (!cfg_has_children() || cfg_is_root()) return;
    if (!up) {
        for (auto &c : d_child) {
            if (c.state == CH_FREE || !(g_cfg.child_alt_mask & (1u << c.id))) continue;
            LOGJ("CHILD_RELEASE", "\"node\":\"%c\",\"why\":\"no_parent\"", node_name(c.id));
            gap_disconnect(c.con);
        }
        if (d_connecting && (g_cfg.child_alt_mask & (1u << d_connecting_id))) gap_connect_cancel();
    }
    update_scan();
}

void downlink_set_deny(uint8_t mask) {
    d_deny_mask = mask;
    LOGJ("DENY", "\"mask\":%u", mask);
    for (auto &c : d_child)
        if (c.state != CH_FREE && (mask & (1u << c.id))) {
            LOGJ("CHILD_RELEASE", "\"node\":\"%c\",\"why\":\"deny\"", node_name(c.id));
            gap_disconnect(c.con);
        }
    if (d_connecting && (mask & (1u << d_connecting_id))) gap_connect_cancel();
    update_scan();
}

int downlink_ready_count() {
    int n = 0;
    for (auto &c : d_child)
        if (c.state == CH_READY) n++;
    return n;
}

void downlink_tick() {
    for (auto &c : d_child)
        if (c.state == CH_READY) gap_read_rssi(c.con);
    if (!cfg_is_root()) {
        LOGJ("RELAY_STATS", "\"fwd\":%" PRIu32 ",\"ttl_drop\":%" PRIu32 ",\"dup\":%" PRIu32 ",\"qfull\":%" PRIu32
             ",\"children\":%d",
             d_relay_fwd, d_relay_ttl_drop, d_relay_dup, d_relay_qfull, downlink_ready_count());
    }
    update_scan();  // phòng trường hợp lần quét trước bị dừng
}
