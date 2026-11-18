# sleepnode: firmware thử nghiệm chu kỳ THỨC -> ĐO -> PHÁT BLE -> NGỦ SÂU cho node lá.
# Độc lập với pico2w-wsn (không đổi firmware mạng đang chạy thực nghiệm).
#   SLEEP_MODE = PSTATE (ngủ sâu nhất, thức dậy = khởi động lại) | DORMANT (giữ RAM) | AWAKE (chỉ tắt radio, CPU chạy)
#   SLEEP_PERIOD_MS = chu kỳ gửi; SLEEP_ADV_MS = thời gian phát quảng bá mỗi lần thức
cmake_minimum_required(VERSION 3.13)
set(CMAKE_C_STANDARD 11)
set(PICO_BOARD pico2_w CACHE STRING "Board type")
set(SLEEP_MODE "PSTATE" CACHE STRING "PSTATE|DORMANT|AWAKE")
set(SLEEP_PERIOD_MS 10000 CACHE STRING "chu ky gui (ms)")
set(SLEEP_ADV_MS 300 CACHE STRING "thoi gian phat quang ba moi lan thuc (ms)")
set(SLEEP_LOG 0 CACHE STRING "1 = in log USB (ton them dong, chi de go loi)")
set(SLEEP_ADAPT 0 CACHE STRING "1 = chi bat radio khi LDR doi > SLEEP_DELTA hoac du SLEEP_HEARTBEAT_N chu ky")
set(SLEEP_DELTA 40 CACHE STRING "nguong doi LDR (ADC tho)")
set(SLEEP_HEARTBEAT_N 30 CACHE STRING "so chu ky toi da khong gui")
set(SLEEP_TEST_CYCLES 0 CACHE STRING "0 = chay mai; N = sau N chu ky thi thuc han, bat USB (de nap lai bang picotool -f)")
include(pico_sdk_import.cmake)
project(sleepnode C CXX ASM)
pico_sdk_init()
add_executable(sleepnode sleepnode.c)
target_compile_definitions(sleepnode PRIVATE
    SLEEP_MODE_${SLEEP_MODE}=1 SLEEP_MODE_NAME="${SLEEP_MODE}"
    SLEEP_PERIOD_MS=${SLEEP_PERIOD_MS} SLEEP_ADV_MS=${SLEEP_ADV_MS} SLEEP_LOG=${SLEEP_LOG}
    SLEEP_TEST_CYCLES=${SLEEP_TEST_CYCLES}
    SLEEP_ADAPT=${SLEEP_ADAPT} SLEEP_DELTA=${SLEEP_DELTA} SLEEP_HEARTBEAT_N=${SLEEP_HEARTBEAT_N})
target_include_directories(sleepnode PRIVATE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(sleepnode pico_stdlib pico_unique_id pico_rand hardware_adc hardware_i2c hardware_powman
    pico_low_power pico_cyw43_arch_none pico_btstack_ble pico_btstack_cyw43)
# Luon link USB stdio nhung chi khoi dong khi SLEEP_LOG=1 hoac het SLEEP_TEST_CYCLES (khong ton dong luc chay that)
pico_enable_stdio_usb(sleepnode 1)
pico_enable_stdio_uart(sleepnode 0)
pico_add_extra_outputs(sleepnode)
