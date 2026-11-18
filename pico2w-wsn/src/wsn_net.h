// wsn_net.h — giao diện giữa các khối firmware.
//
//   wsn_source   : dữ liệu của chính node (tạo DATA/STATS, giữ gói chưa có ACK, gửi lại)
//   wsn_uplink   : phía "con" của liên kết — Peripheral + GATT Server, nối tới node cha
//   wsn_downlink : phía "cha" của liên kết — Central + GATT Client, nối tới các node con
//   wsn_root     : xử lý ở Root (kiểm tra thứ tự, lọc trùng, gửi ACK_ROOT, log JSON)
//   relay (trong wsn_downlink): chuyển tiếp gói con lên cha, ACK từ cha xuống con
//
// Mọi hàm ở đây chạy trong ngữ cảnh BTstack (callback/timer), không bao giờ chặn.
#pragma once
#include <stdint.h>

#include "btstack.h"
#include "wsn_proto.h"

// ---- uplink (tới node cha)
void uplink_start();
bool uplink_ready();                                  // đã kết nối và cha đã subscribe
bool uplink_enqueue(const uint8_t *frame, uint16_t len);  // false = hàng đợi đầy
bool uplink_queued(uint8_t source_id, uint32_t boot_id, uint32_t seq);  // gói DATA đang chờ gửi?
bool uplink_owns(hci_con_handle_t con);
void uplink_on_connected(hci_con_handle_t con, uint8_t *packet);
void uplink_on_disconnected(uint8_t reason);
void uplink_on_rssi(int8_t rssi);
void uplink_tick();                                   // gọi mỗi chu kỳ STATS: đọc RSSI
int8_t uplink_rssi();
uint8_t uplink_parent_id();                           // 0xFF = chưa biết
uint16_t uplink_queue_full_count();
uint8_t uplink_parent_lost_count();
void uplink_test_drop(uint32_t hold_ms);              // test: tự cắt liên kết lên cha, không quảng bá hold_ms
uint16_t uplink_att_read(hci_con_handle_t con, uint16_t handle, uint16_t offset, uint8_t *buf,
                         uint16_t size);
int uplink_att_write(hci_con_handle_t con, uint16_t handle, uint16_t mode, uint16_t offset,
                     uint8_t *buf, uint16_t size);
void uplink_att_packet(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size);

// ---- downlink (tới các node con)
void downlink_start();
void downlink_on_adv(uint8_t *packet);
void downlink_on_connection_complete(uint8_t *packet);
bool downlink_on_disconnected(hci_con_handle_t con, uint8_t reason);  // false = không phải con
void downlink_on_rssi(hci_con_handle_t con, int8_t rssi);
void downlink_tick();                                 // gọi mỗi chu kỳ STATS
bool downlink_send(uint8_t child_id, const uint8_t *frame, uint16_t len);  // gửi xuống một con
void downlink_route_ack(const AckRootPacket *ack);    // relay: ACK của node khác -> đúng con
int downlink_ready_count();
void downlink_on_uplink(bool up);                     // relay: có / mất cha (nhả con có cha dự phòng)
int8_t downlink_rssi(uint8_t child_id);
void downlink_set_deny(uint8_t mask);                 // test: không nhận / nhả các con này (giả lập ở quá xa)

// ---- source (dữ liệu của chính node)
void source_start();
void source_on_ack(const AckRootPacket *ack);
void source_on_parent_change();
void source_set_period(uint32_t ms);                  // test E5: đổi chu kỳ tạo DATA lúc chạy

// ---- root
void root_start();
void root_on_frame(uint8_t from_child, const uint8_t *frame, uint16_t len);
void root_on_child_connected(uint8_t child_id);
void root_set_ack_drop(uint8_t percent);              // test E4: Root cố ý bỏ ACK với xác suất này
