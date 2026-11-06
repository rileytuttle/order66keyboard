#!/usr/bin/env bash
# Build order66 firmware. Run via:
#   docker compose run --rm zmk scripts/build.sh
# or natively, if you already have west + the Zephyr SDK set up:
#   ./scripts/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .west ]; then
    west init -l config
    west update
fi

# zephyr-export registers Zephyr in CMake's user package registry (under
# $HOME), which doesn't persist across `docker compose run --rm` containers
# since only this repo is bind-mounted -- so run it every time; it's cheap.
west zephyr-export

west build -s zmk/app -p -b "nice_nano//zmk" -- \
    -DSHIELD="order66 nice_view_adapter nice_view" \
    -DZMK_EXTRA_MODULES="$(pwd)/zmk-modules/order66-shield"

echo
echo "Built: $(pwd)/build/zephyr/zmk.uf2"
echo "Double-tap reset on the nice!nano, then copy that file to the drive that appears."
