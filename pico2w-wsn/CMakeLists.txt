# pico2w-wsn: firmware chung cho cả 4 board (Node A/B/C + Root).
# Một file UF2 cho mọi board; vai trò lấy từ serial flash lúc chạy (wsn_config.cpp).
#
# Tùy chọn lúc build (cmake -D...):
#   WSN_TOPOLOGY = PAIR | CHAIN | STAR | DIAMOND | MESH   (mặc định PAIR)
#     MESH: node nào cũng nhận được node khác làm cha, tự chọn lại đường khi mất cha (order = các node tham gia)
#   WSN_ORDER    = thứ tự node, từ node lá về phía Root. Ví dụ:
#                  PAIR "A" (A->R), CHAIN "CBA" (C->B->A->R), CHAIN "CB" (C->B->R),
#                  STAR "ABC" (mỗi node ->R), DIAMOND "CAB" (C->A|B, A->R, B->R)
#   WSN_POWER    = FAST | LOW_POWER                  (mặc định FAST)

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.1)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.1)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico2_w CACHE STRING "Board type")

set(WSN_TOPOLOGY "PAIR" CACHE STRING "PAIR|CHAIN|STAR|DIAMOND|MESH")
set(WSN_ORDER "" CACHE STRING "Node order, leaf first (empty = default per topology)")
set(WSN_POWER "FAST" CACHE STRING "FAST|LOW_POWER")

if(WSN_ORDER STREQUAL "")
    if(WSN_TOPOLOGY STREQUAL "PAIR")
        set(WSN_ORDER_EFF "A")
    elseif(WSN_TOPOLOGY STREQUAL "DIAMOND")
        set(WSN_ORDER_EFF "CAB")
    elseif(WSN_TOPOLOGY STREQUAL "MESH")
        set(WSN_ORDER_EFF "ABC")
    else()
        set(WSN_ORDER_EFF "CBA")
    endif()
else()
    set(WSN_ORDER_EFF "${WSN_ORDER}")
endif()

include(pico_sdk_import.cmake)

project(pico2w-wsn C CXX ASM)

pico_sdk_init()

# Mã commit git đưa vào dòng log BOOT để biết board đang chạy bản nào ("+" = có sửa chưa commit).
execute_process(COMMAND git rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR} OUTPUT_VARIABLE WSN_GIT OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET)
execute_process(COMMAND git status --porcelain -- .
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR} OUTPUT_VARIABLE WSN_GIT_DIRTY ERROR_QUIET)
if(NOT WSN_GIT_DIRTY STREQUAL "")
    set(WSN_GIT "${WSN_GIT}+")
endif()

add_executable(pico2w-wsn
    src/main.cpp
    src/wsn_config.cpp
    src/wsn_sensors.cpp
    src/wsn_source.cpp
    src/wsn_uplink.cpp
    src/wsn_downlink.cpp
    src/wsn_root.cpp
)

target_compile_definitions(pico2w-wsn PRIVATE
    WSN_TOPOLOGY_${WSN_TOPOLOGY}=1
    WSN_TOPOLOGY_NAME="${WSN_TOPOLOGY}"
    WSN_ORDER="${WSN_ORDER_EFF}"
    WSN_POWER_${WSN_POWER}=1
    WSN_POWER_NAME="${WSN_POWER}"
    WSN_GIT="${WSN_GIT}"
)

pico_set_program_name(pico2w-wsn "pico2w-wsn")
pico_set_program_version(pico2w-wsn "0.1")

pico_enable_stdio_uart(pico2w-wsn 0)
pico_enable_stdio_usb(pico2w-wsn 1)

target_include_directories(pico2w-wsn PRIVATE ${CMAKE_CURRENT_LIST_DIR} ${CMAKE_CURRENT_LIST_DIR}/src)

target_link_libraries(pico2w-wsn
    pico_stdlib
    pico_unique_id
    pico_rand
    hardware_adc
    hardware_i2c
    pico_cyw43_arch_none
    pico_btstack_ble
    pico_btstack_cyw43
)

pico_btstack_make_gatt_header(pico2w-wsn PRIVATE "${CMAKE_CURRENT_LIST_DIR}/wsn.gatt")

pico_add_extra_outputs(pico2w-wsn)
