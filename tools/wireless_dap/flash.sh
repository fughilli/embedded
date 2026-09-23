#!/usr/bin/env bash
# Flash a build from build.sh.
#   tools/wireless_dap/flash.sh <build-dir> <serial-port> [--erase]
# By default only the bootloader, partition table and app are written (flash_args),
# so the NVS partition, including saved Wi-Fi credentials, survives. --erase wipes
# the whole chip first. 460800 baud: CH340 USB-serial clones corrupt at 921600.
set -euo pipefail
dir=$1 port=$2
esptool=(nix --extra-experimental-features "nix-command flakes" shell nixpkgs#esptool -c esptool.py)
if [ "${3:-}" = "--erase" ]; then
  "${esptool[@]}" --port "$port" -b 460800 erase_flash
fi
cd "$dir"
"${esptool[@]}" --port "$port" -b 460800 write_flash @flash_args
