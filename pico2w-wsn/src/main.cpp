// main.cpp — khởi động: xác định vai trò từ serial, bật BTstack, chia sự kiện HCI cho uplink/downlink.
//
// Một board có thể vừa là con (uplink, Peripheral, nối tới cha) vừa là cha (downlink, Central,
// nối tới các con) — đó là relay. Sự kiện kết nối được chia theo vai trò của kết nối đó:
// role = SLAVE (Peripheral) -> uplink, role = MASTER (Central) -> downlink.
// Sau khi khởi động, mọi việc chạy trong callback/timer của BTstack; vòng lặp main chỉ ngủ.
#include <stdio.h>
#include <string.h>

#include "btstack.h"
#include "pico/cyw43_arch.h"
#include "pico/rand.h"
#include "pico/stdlib.h"
#include "wsn.h"  // sinh từ wsn.gatt: profile_data
#include "wsn_config.h"
#include "wsn_net.h"
#include "wsn_sensors.h"

static btstack_packet_callback_registration_t g_hci_cb;
static btstack_timer_source_t g_led_timer;
static uint32_t g_led_tick = 0;

static void print_boot(const char *state) {
    bd_addr_t addr;
    gap_local_bd_addr(addr);
    LOGJ("BOOT",
         "\"state\":\"%s\",\"node\":\"%c\",\"node_id\":%u,\"serial\":\"%s\",\"known\":%d,\"boot\":%" PRIu32
         ",\"fw\":\"%s\",\"topology\":\"%s\",\"order\":\"%s\",\"power\":\"%s\",\"parent_mask\":%u,"
         "\"child_mask\":%u,\"child_alt_mask\":%u,\"depth\":%u,\"ina219\":%d,\"bd_addr\":\"%s\"",
         state, g_cfg.name, g_cfg.id, g_cfg.serial, g_cfg.known ? 1 : 0, g_boot_id, WSN_GIT, WSN_TOPOLOGY_NAME,
         WSN_ORDER, WSN_POWER_NAME, g_cfg.parent_mask, g_cfg.child_mask, g_cfg.child_alt_mask, g_cfg.depth,
         sensors_has_ina219() ? 1 : 0, bd_addr_to_str(addr));
}

static void hci_handler(uint8_t packet_type, uint16_t, uint8_t *packet, uint16_t) {
    if (packet_type != HCI_EVENT_PACKET) return;
    switch (hci_event_packet_get_type(packet)) {
    case BTSTACK_EVENT_STATE:
        if (btstack_event_state_get_state(packet) != HCI_STATE_WORKING) break;
        print_boot("BLE_READY");
        if (!cfg_has_parent() && !cfg_is_root()) {
            LOGJ("IDLE", "\"msg\":\"board not used in this topology\"");
            break;
        }
        if (cfg_has_children()) downlink_start();
        if (cfg_has_parent()) {
            uplink_start();
            source_start();
        }
        if (cfg_is_root()) root_start();
        break;
    case HCI_EVENT_META_GAP:
        if (hci_event_gap_meta_get_subevent_code(packet) != GAP_SUBEVENT_LE_CONNECTION_COMPLETE) break;
        // Kết nối thất bại chỉ xảy ra với lệnh gap_connect của phía Central
        if (gap_subevent_le_connection_complete_get_status(packet) != ERROR_CODE_SUCCESS ||
            gap_subevent_le_connection_complete_get_role(packet) == HCI_ROLE_MASTER) {
            downlink_on_connection_complete(packet);
        } else {
            uplink_on_connected(gap_subevent_le_connection_complete_get_connection_handle(packet), packet);
        }
        break;
    case GAP_EVENT_ADVERTISING_REPORT:
        if (cfg_has_children()) downlink_on_adv(packet);
        break;
    case HCI_EVENT_DISCONNECTION_COMPLETE: {
        hci_con_handle_t con = hci_event_disconnection_complete_get_connection_handle(packet);
        uint8_t reason = hci_event_disconnection_complete_get_reason(packet);
        if (uplink_owns(con)) {
            uplink_on_disconnected(reason);
        } else {
            downlink_on_disconnected(con, reason);
        }
        break;
    }
    case GAP_EVENT_RSSI_MEASUREMENT: {
        hci_con_handle_t con = gap_event_rssi_measurement_get_con_handle(packet);
        int8_t rssi = (int8_t)gap_event_rssi_measurement_get_rssi(packet);
        if (uplink_owns(con)) uplink_on_rssi(rssi);
        else downlink_on_rssi(con, rssi);
        break;
    }
    default:
        break;
    }
}

// Lệnh test qua USB, mỗi lệnh một dòng (máy tính gửi qua tools/logcap.py, xem docs/HUONG_DAN_WSN.md):
//   u            node tự cắt liên kết lên cha, không quảng bá 15 s (giả lập mất liên kết tới cha)
//   period <ms>  node đổi chu kỳ tạo DATA (E5: tăng tốc độ gửi)
//   ackdrop <%>  Root cố ý bỏ ACK_ROOT với xác suất % (E4: ép mất ACK -> retry, gói trùng)
//   deny <ABC|-> node (thường là Root) coi như không nghe thấy các node này: nhả nếu đang nối, không nhận lại
//                (MESH: giả lập node ở quá xa Root -> phải đi vòng qua node khác). "deny -" = bỏ chặn
static char con_buf[32];
static int con_len = 0;

static void run_command(const char *cmd) {
    unsigned v = 0;
    if (strcmp(cmd, "u") == 0 && cfg_has_parent()) {
        uplink_test_drop(15000);
    } else if (sscanf(cmd, "period %u", &v) == 1 && cfg_has_parent()) {
        source_set_period(v);
    } else if (strncmp(cmd, "deny ", 5) == 0 && cfg_has_children()) {
        uint8_t mask = 0;
        for (const char *p = cmd + 5; *p; p++)
            for (uint8_t i = 1; i <= MAX_NODE_ID; i++)
                if (node_name(i) == *p) mask |= (uint8_t)(1u << i);
        downlink_set_deny(mask);
    } else if (sscanf(cmd, "ackdrop %u", &v) == 1 && cfg_is_root()) {
        root_set_ack_drop((uint8_t)(v > 100 ? 100 : v));
    } else {
        LOGJ("CMD_UNKNOWN", "\"cmd\":\"%s\"", cmd);
    }
}

static void poll_console() {
    int ch;
    while ((ch = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        if (ch == '\n' || ch == '\r') {
            con_buf[con_len] = 0;
            if (con_len) run_command(con_buf);
            con_len = 0;
        } else if (con_len < (int)sizeof(con_buf) - 1 && ch >= 0x20 && ch < 0x7F) {
            con_buf[con_len++] = (char)ch;
        }
    }
}

// LED trên board (qua CYW43): nhấp nháy = chưa có liên kết; sáng liên tục = đang có liên kết.
static void led_timer(btstack_timer_source_t *ts) {
    g_led_tick++;
    poll_console();
    bool linked = cfg_is_root() ? downlink_ready_count() > 0 : uplink_ready();
    bool on = linked ? true : (g_led_tick & 1);
    if (!cfg_has_parent() && !cfg_is_root()) on = (g_led_tick % 8) == 0;  // board rảnh: chớp thưa
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
    btstack_run_loop_set_timer(ts, 500);
    btstack_run_loop_add_timer(ts);
}

int main() {
    stdio_init_all();
    if (cyw43_arch_init()) {
        printf("{\"type\":\"FATAL\",\"msg\":\"cyw43 init failed\"}\n");
        return -1;
    }
    // Chờ tối đa 3 s cho máy tính mở cổng COM để không mất dòng BOOT (chạy pin thì bỏ qua).
    for (int i = 0; i < 30 && !stdio_usb_connected(); i++) sleep_ms(100);

    g_boot_id = get_rand_32();
    config_init();
    sensors_init();

    l2cap_init();
    sm_init();
    att_server_init(profile_data, uplink_att_read, uplink_att_write);
    gatt_client_init();

    g_hci_cb.callback = &hci_handler;
    hci_add_event_handler(&g_hci_cb);
    att_server_register_packet_handler(&uplink_att_packet);

    btstack_run_loop_set_timer(&g_led_timer, 500);
    btstack_run_loop_set_timer_handler(&g_led_timer, led_timer);
    btstack_run_loop_add_timer(&g_led_timer);

    print_boot("START");
    hci_power_control(HCI_POWER_ON);

    while (true) sleep_ms(1000);
}
