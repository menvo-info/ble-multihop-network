// wsn_proto.h — định dạng gói tin trên không (BLE GATT).
//
// Mọi gói <= 20 byte để vừa một notification khi ATT MTU mặc định (23 - 3 = 20 byte).
// Byte đầu tiên của mọi gói là "hdr" = (version << 4) | type, nên bên nhận chỉ cần đọc
// byte đầu là biết loại gói. Số nhiều byte theo little-endian (đúng thứ tự bộ nhớ của RP2350).
//
// Chiều đi lên (notify trên characteristic DATA):   DATA, STATS
// Chiều đi xuống (write trên characteristic ACK):   ACK_ROOT, HELLO
#pragma once
#include <stdint.h>

static constexpr uint8_t PROTO_VERSION = 1;

enum MsgType : uint8_t {
    MSG_DATA = 1,      // số liệu cảm biến của một node nguồn
    MSG_ACK_ROOT = 2,  // Root xác nhận đã nhận một gói DATA
    MSG_STATS = 3,     // thống kê định kỳ của một node (để tính chỉ số chỉ từ dữ liệu Root)
    MSG_HELLO = 4,     // node cha báo node_id của mình cho node con ngay sau khi subscribe
};

static inline uint8_t make_hdr(uint8_t type) { return (uint8_t)((PROTO_VERSION << 4) | type); }
static inline uint8_t hdr_version(uint8_t hdr) { return hdr >> 4; }
static inline uint8_t hdr_type(uint8_t hdr) { return hdr & 0x0F; }

// Cờ trong DataPacket.flags
enum DataFlags : uint8_t {
    FLAG_FAKE = 1 << 0,        // board không có cảm biến: giá trị là giả
    FLAG_RETRY = 1 << 1,       // đây là lần gửi lại (danh tính gói giữ nguyên)
    FLAG_SENSOR_ERR = 1 << 2,  // có mạch nhưng cảm biến đọc lỗi (vd. LDR ~0)
    FLAG_LOW_POWER = 1 << 3,   // node đang chạy chế độ LOW_POWER
};

static constexpr uint8_t DEFAULT_TTL = 4;  // đủ cho chuỗi dài nhất C -> B -> A -> R (3 hop)

#pragma pack(push, 1)

// Danh tính một gói = (source_id, boot_id, seq). boot_id ngẫu nhiên mỗi lần khởi động,
// nên seq bắt đầu lại từ 0 sau reset mà Root vẫn phân biệt được.
struct DataPacket {
    uint8_t hdr;
    uint8_t source_id;
    uint8_t ttl;        // relay giảm 1 mỗi lần chuyển tiếp; về 0 thì bỏ
    uint8_t hop;        // số lần đã chuyển tiếp (0 = gửi thẳng tới Root)
    uint8_t flags;
    uint8_t parent_id;  // node cha trực tiếp của node nguồn lúc gửi (Root dùng để phát hiện đổi tuyến)
    uint32_t boot_id;
    uint32_t seq;
    uint16_t ldr;            // ADC thô 12 bit
    int16_t current_ma_x10;  // dòng INA219, đơn vị 0.1 mA (đã trừ offset)
    uint16_t vbat_mv;        // điện áp bus INA219
};

struct AckRootPacket {
    uint8_t hdr;
    uint8_t source_id;  // node nguồn của gói DATA được xác nhận
    uint16_t reserved;
    uint32_t boot_id;
    uint32_t seq;
};

struct StatsPacket {
    uint8_t hdr;
    uint8_t source_id;
    int8_t rssi_dbm;      // RSSI kết nối tới node cha (0 = chưa đo)
    uint8_t parent_lost;  // số lần mất kết nối với cha (cộng dồn, bão hòa 255)
    uint32_t boot_id;
    uint32_t generated;    // số gói DATA đã tạo (cộng dồn từ lúc boot)
    uint16_t retries;      // số lần gửi lại (cộng dồn)
    uint16_t queue_full;   // số lần hàng đợi gửi lên cha bị đầy (cộng dồn)
    uint16_t rtt_avg_ms;   // ACK RTT trung bình trong chu kỳ STATS vừa qua (0 = không có)
    int16_t current_avg_x10;  // dòng trung bình trong chu kỳ, 0.1 mA (INT16_MIN = không có INA219)
};

struct HelloPacket {
    uint8_t hdr;
    uint8_t parent_id;
    uint8_t path_mask;  // các node từ cha lên Root, gồm cả cha và Root (bit i = node i). Con dùng để
                        // biết số hop và chống vòng lặp ở MESH; các topology cố định bỏ qua.
};

#pragma pack(pop)

static_assert(sizeof(DataPacket) == 20, "DATA must fit a default-MTU notification");
static_assert(sizeof(AckRootPacket) == 12, "ACK_ROOT size");
static_assert(sizeof(StatsPacket) == 20, "STATS must fit a default-MTU notification");
static_assert(sizeof(HelloPacket) == 3, "HELLO size (nhận cả bản cũ 2 byte)");

static constexpr uint16_t MAX_FRAME = 20;
