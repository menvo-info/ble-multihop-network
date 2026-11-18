#!/usr/bin/env bash
# Build pico2w-wsn cho một cấu hình. Mỗi cấu hình một thư mục build riêng.
#   tools/build.sh [TOPOLOGY] [ORDER] [POWER]
#   vd: tools/build.sh PAIR A FAST        -> pico2w-wsn/build-PAIR-A-FAST/pico2w-wsn.uf2
#       tools/build.sh CHAIN CBA LOW_POWER
set -euo pipefail
TOPO=${1:-PAIR}
ORDER=${2:-}
POWER=${3:-FAST}
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
P="$HOME/.pico-sdk"
export PATH="$P/cmake/v4.3.4/bin:$P/ninja/v1.13.2:$P/toolchain/15_2_Rel1/bin:$PATH"
export PICO_SDK_PATH="$P/sdk/2.3.1"
NAME="${TOPO}-${ORDER:-default}-${POWER}"
B="$ROOT_DIR/pico2w-wsn/build-$NAME"
cmake -S "$ROOT_DIR/pico2w-wsn" -B "$B" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DWSN_TOPOLOGY="$TOPO" -DWSN_ORDER="$ORDER" -DWSN_POWER="$POWER" \
    -Dpicotool_DIR="$P/picotool/2.3.1/picotool" > "$B.cmake.log" 2>&1 || { tail -30 "$B.cmake.log"; exit 1; }
# Luôn chạy lại cmake để mã commit git trong log BOOT là mới nhất
if ! ninja -C "$B" > "$B.ninja.log" 2>&1; then
    grep -E "error|FAILED" "$B.ninja.log" | head -40; exit 1
fi
grep -E "warning" "$B.ninja.log" | grep -v "lib/btstack\|pico-sdk" | head -20 || true
echo "UF2: $B/pico2w-wsn.uf2"
