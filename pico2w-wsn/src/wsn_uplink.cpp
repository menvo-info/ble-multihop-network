// wsn_uplink.cpp — phía node con của một liên kết: Peripheral + GATT Server.
//
// Node quảng bá service UUID + node_id (manufacturer data) để đúng node cha kết nối tới.
// Khi cha subscribe characteristic DATA, node gửi các gói trong hàng đợi bằng notify.
// Notify chỉ được gửi khi BTstack báo ATT_EVENT_CAN_SEND_NOW (bộ đệm controller còn chỗ),
// nên không bao giờ chặn. Cha gửi ACK_ROOT / HELLO xuống bằng write-without-response.
#include <string.h>

#include "wsn_config.h"
#include "wsn_net.h"
#include "wsn.h"  // sinh từ wsn.gatt

// Handle sinh tự động từ wsn.gatt (pico_btstack_make_gatt_header)
static constexpr uint16_t DATA_VALUE_HANDLE =
    ATT_CHARACTERISTIC_A7E50001_3C1D_4B8E_9F21_7D0C5E2B9A10_01_VALUE_HANDLE;
static constexpr uint16_t DATA_CCCD_HANDLE =
    ATT_CHARACTERISTIC_A7E50001_3C1D_4B8E_9F21_7D0C5E2B9A10_01_CLIENT_CONFIGURATION_HANDLE;
static constexpr uint16_t ACK_VALUE_HANDLE =
    ATT_CHARACTERISTIC_A7E50002_3C1D_4B8E_9F21_7D0C5E2B9A10_01_VALUE_HANDLE;

static const uint8_t SERVICE_UUID[16] = {0xA7, 0xE5, 0x00, 0x00, 0x3C, 0x1D, 0x4B, 0x8E,
                                         0x9F, 0x21, 0x7D, 0x0C, 0x5E, 0x2B, 0x9A, 0x10};

// ---- hàng đợi gửi lên cha (vòng tròn, kích thước cố định)
static constexpr int QUEUE_LEN = 16;
struct Frame {
    uint8_t len;
    uint8_t b[MAX_FRAME];
};
static Frame q_buf[QUEUE_LEN];
static int q_head = 0, q_count = 0;

static hci_con_handle_t u_con = HCI_CON_HANDLE_INVALID;
static bool u_notify_on = false;
static bool u_can_send_requested = false;
static uint8_t u_parent_id = 0xFF;
static uint8_t u_prev_parent = 0xFF;  // cha của lần kết nối trước (log PARENT)
static uint32_t u_adv_hold_until = 0;  // test: không quảng bá tới thời điểm này
static btstack_timer_source_t u_hold_timer;
static int8_t u_rssi = 0;
static uint16_t u_queue_full = 0;
static uint8_t u_parent_lost = 0;
static uint32_t u_connected_at = 0;
static uint8_t last_sent[MAX_FRAME];  // trả về khi cha đọc (READ) characteristic DATA

static uint8_t adv_data[3 + 18 + 5];
static uint8_t scan_rsp[2 + 5];

static void request_send() {
    if (uplink_ready() && q_count > 0 && !u_can_send_requested) {
        u_can_send_requested = true;
        // BTstack sẽ gửi ATT_EVENT_CAN_SEND_NOW khi có thể notify
        att_server_request_can_send_now_event(u_con);
    }
}

void uplink_start() {
    uint8_t *p = adv_data;
    *p++ = 2;  // Flags: LE General Discoverable, không hỗ trợ BR/EDR
    *p++ = BLUETOOTH_DATA_TYPE_FLAGS;
    *p++ = 0x06;
    *p++ = 17;  // 128-bit service UUID (thứ tự byte đảo khi quảng bá)
    *p++ = BLUETOOTH_DATA_TYPE_COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS;
    reverse_128(SERVICE_UUID, p);
    p += 16;
    *p++ = 4;  // Manufacturer data: company 0xFFFF (dùng thử nghiệm) + node_id
    *p++ = BLUETOOTH_DATA_TYPE_MANUFACTURER_SPECIFIC_DATA;
    *p++ = 0xFF;
    *p++ = 0xFF;
    *p++ = g_cfg.id;

    scan_rsp[0] = 6;
    scan_rsp[1] = BLUETOOTH_DATA_TYPE_COMPLETE_LOCAL_NAME;
    memcpy(&scan_rsp[2], "WSN-", 4);
    scan_rsp[6] = (uint8_t)g_cfg.name;

    bd_addr_t null_addr = {0};
    // ADV_IND (0) — cho phép kết nối; kênh 37/38/39 (0x07)
    gap_advertisements_set_params(g_cfg.pw.adv_interval, g_cfg.pw.adv_interval, 0, 0, null_addr,
                                  0x07, 0x00);
    gap_advertisements_set_data(sizeof(adv_data), adv_data);
    gap_scan_response_set_data(sizeof(scan_rsp), scan_rsp);
    gap_advertisements_enable(1);
    LOGJ("ADV_START", "\"node\":\"%c\",\"adv_ms\":%u", g_cfg.name,
         (unsigned)(g_cfg.pw.adv_interval * 625 / 1000));
}

// Sẵn sàng gửi = đã kết nối, cha đã subscribe VÀ đã nhận HELLO (biết cha là ai), để mọi gói DATA
// mang đúng parent_id (trước đây vài gói gửi trong ~100 ms giữa subscribe và HELLO mang parent "?").
bool uplink_ready() { return u_con != HCI_CON_HANDLE_INVALID && u_notify_on && u_parent_id != 0xFF; }
bool uplink_owns(hci_con_handle_t con) { return con != HCI_CON_HANDLE_INVALID && con == u_con; }
int8_t uplink_rssi() { return u_rssi; }
uint8_t uplink_parent_id() { return u_parent_id; }
uint16_t uplink_queue_full_count() { return u_queue_full; }
uint8_t uplink_parent_lost_count() { return u_parent_lost; }
void uplink_on_rssi(int8_t rssi) { u_rssi = rssi; }

bool uplink_enqueue(const uint8_t *frame, uint16_t len) {
    if (q_count >= QUEUE_LEN) {
        if (u_queue_full < 0xFFFF) u_queue_full++;
        return false;
    }
    Frame &f = q_buf[(q_head + q_count) % QUEUE_LEN];
    f.len = (uint8_t)len;
    memcpy(f.b, frame, len);
    q_count++;
    request_send();
    return true;
}

bool uplink_queued(uint8_t source_id, uint32_t boot_id, uint32_t seq) {
    for (int i = 0; i < q_count; i++) {
        const Frame &f = q_buf[(q_head + i) % QUEUE_LEN];
        if (f.len != sizeof(DataPacket) || hdr_type(f.b[0]) != MSG_DATA) continue;
        DataPacket d;
        memcpy(&d, f.b, sizeof(d));
        if (d.source_id == source_id && d.boot_id == boot_id && d.seq == seq) return true;
    }
    return false;
}

void uplink_on_connected(hci_con_handle_t con, uint8_t *packet) {
    u_con = con;
    u_notify_on = false;
    u_can_send_requested = false;
    u_parent_id = 0xFF;
    u_connected_at = now_ms();
    bd_addr_t peer;
    gap_subevent_le_connection_complete_get_peer_address(packet, peer);
    uint16_t itv = gap_subevent_le_connection_complete_get_conn_interval(packet);
    LOGJ("CONNECTED", "\"link\":\"parent\",\"peer\":\"%s\",\"interval_ms\":%u.%02u", bd_addr_to_str(peer),
         itv * 125 / 100, (itv * 125) % 100);
}

void uplink_on_disconnected(uint8_t reason) {
    LOGJ("DISCONNECTED", "\"link\":\"parent\",\"parent\":\"%c\",\"reason\":\"0x%02x\",\"up_ms\":%" PRIu32,
         node_name(u_parent_id), reason, now_ms() - u_connected_at);
    u_con = HCI_CON_HANDLE_INVALID;
    u_notify_on = false;
    u_can_send_requested = false;
    if (u_parent_id != 0xFF) u_prev_parent = u_parent_id;
    cfg_set_path(0);  // MESH: hết đường lên Root
    if (u_parent_lost < 0xFF) u_parent_lost++;
    downlink_on_uplink(false);
    // Gói đã nằm trong hàng đợi giữ nguyên; gửi tiếp khi có cha mới.
    if ((int32_t)(now_ms() - u_adv_hold_until) >= 0) gap_advertisements_enable(1);
}

static void hold_done(btstack_timer_source_t *) {
    LOGJ("TEST_HOLD_END", "\"adv\":1");
    if (u_con == HCI_CON_HANDLE_INVALID) gap_advertisements_enable(1);
}

void uplink_test_drop(uint32_t hold_ms) {
    LOGJ("TEST_DROP_UPLINK", "\"parent\":\"%c\",\"hold_ms\":%" PRIu32 ",\"connected\":%d", node_name(u_parent_id),
         hold_ms, u_con != HCI_CON_HANDLE_INVALID ? 1 : 0);
    u_adv_hold_until = now_ms() + hold_ms;
    gap_advertisements_enable(0);
    if (u_con != HCI_CON_HANDLE_INVALID) gap_disconnect(u_con);
    btstack_run_loop_remove_timer(&u_hold_timer);
    btstack_run_loop_set_timer(&u_hold_timer, hold_ms);
    btstack_run_loop_set_timer_handler(&u_hold_timer, hold_done);
    btstack_run_loop_add_timer(&u_hold_timer);
}

void uplink_tick() {
    if (u_con != HCI_CON_HANDLE_INVALID) gap_read_rssi(u_con);  // kết quả về GAP_EVENT_RSSI_MEASUREMENT
}

uint16_t uplink_att_read(hci_con_handle_t, uint16_t handle, uint16_t offset, uint8_t *buf,
                         uint16_t size) {
    if (handle == DATA_VALUE_HANDLE)
        return att_read_callback_handle_blob(last_sent, sizeof(last_sent), offset, buf, size);
    return 0;
}

int uplink_att_write(hci_con_handle_t con, uint16_t handle, uint16_t, uint16_t, uint8_t *buf,
                     uint16_t size) {
    if (con != u_con) return 0;  // chỉ nhận lệnh từ cha của mình
    if (handle == DATA_CCCD_HANDLE && size >= 2) {
        u_notify_on = little_endian_read_16(buf, 0) == GATT_CLIENT_CHARACTERISTICS_CONFIGURATION_NOTIFICATION;
        LOGJ("SUBSCRIBED", "\"link\":\"parent\",\"notify\":%s", u_notify_on ? "true" : "false");
        request_send();
        return 0;
    }
    if (handle != ACK_VALUE_HANDLE || size < 1) return 0;
    uint8_t type = hdr_type(buf[0]);
    if (hdr_version(buf[0]) != PROTO_VERSION) {
        LOGJ("RX_BAD", "\"link\":\"parent\",\"hdr\":%u,\"len\":%u", buf[0], size);
        return 0;
    }
    if (type == MSG_HELLO && (size == sizeof(HelloPacket) || size == 2)) {
        uint8_t path = size >= 3 ? buf[2] : (uint8_t)((1u << ROOT_ID) | (1u << buf[1]));
        if (g_cfg.mesh && (path & (1u << g_cfg.id))) {
            // Cha này đang đi lên Root qua chính mình -> nhận thì thành vòng lặp. Cắt, chờ cha khác.
            LOGJ("LOOP_REJECT", "\"parent\":\"%c\",\"path\":%u", node_name(buf[1]), path);
            gap_disconnect(u_con);
            return 0;
        }
        u_parent_id = buf[1];
        cfg_set_path(path);
        LOGJ("PARENT", "\"parent\":\"%c\",\"prev\":\"%c\",\"depth\":%u,\"path\":%u", node_name(u_parent_id),
             node_name(u_prev_parent), g_cfg.depth, path);
        source_on_parent_change();
        downlink_on_uplink(true);
        request_send();  // gói relay đang chờ trong hàng đợi
    } else if (type == MSG_ACK_ROOT && size == sizeof(AckRootPacket)) {
        AckRootPacket ack;
        memcpy(&ack, buf, sizeof(ack));
        if (ack.source_id == g_cfg.id) {
            source_on_ack(&ack);
        } else {
            downlink_route_ack(&ack);  // relay: ACK của node con phía dưới
        }
    } else {
        LOGJ("RX_BAD", "\"link\":\"parent\",\"msg\":%u,\"len\":%u", type, size);
    }
    return 0;
}

// Nhận sự kiện của ATT server (chỉ cần CAN_SEND_NOW).
void uplink_att_packet(uint8_t packet_type, uint16_t, uint8_t *packet, uint16_t) {
    if (packet_type != HCI_EVENT_PACKET) return;
    if (hci_event_packet_get_type(packet) != ATT_EVENT_CAN_SEND_NOW) return;
    u_can_send_requested = false;
    if (!uplink_ready() || q_count == 0) return;
    Frame &f = q_buf[q_head];
    uint8_t status = att_server_notify(u_con, DATA_VALUE_HANDLE, f.b, f.len);
    if (status == ERROR_CODE_SUCCESS) {
        memset(last_sent, 0, sizeof(last_sent));
        memcpy(last_sent, f.b, f.len);
        q_head = (q_head + 1) % QUEUE_LEN;
        q_count--;
    } else {
        LOGJ("TX_FAIL", "\"link\":\"parent\",\"status\":%u", status);
    }
    request_send();
}
