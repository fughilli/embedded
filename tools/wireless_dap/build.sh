#!/usr/bin/env bash
# Build the patched wireless ESP32 DAP firmware in Espressif's ESP-IDF v5.2.1 image.
#   tools/wireless_dap/build.sh [esp32|esp32c3|esp32s3] [out-dir]
# Needs nix (for the patched source) and docker. The source is copied into the
# container rather than bind-mounted, which avoids Docker Desktop file-sharing limits.
set -euo pipefail
target=${1:-esp32}
out=${2:-$PWD/wireless_dap-$target}
here=$(cd "$(dirname "$0")" && pwd)
src=$(nix --extra-experimental-features "nix-command flakes" build --no-link --print-out-paths "$here/../..#wireless-dap-src")

cid=$(docker create -w /project espressif/idf:v5.2.1 bash -c "
  set -e
  git config --global --add safe.directory '*'
  idf.py set-target $target
  idf.py build
  cd build && esptool.py --chip $target merge_bin -o wireless_tools_full.bin @flash_args")
trap 'docker rm -f "$cid" >/dev/null' EXIT
docker cp "$src/." "$cid:/project"
docker start -a "$cid"

mkdir -p "$out"
for f in wireless_tools_esp32.bin wireless_tools_full.bin flash_args bootloader partition_table; do
  docker cp "$cid:/project/build/$f" "$out/"
done
echo "built $target firmware in $out (flash with $here/flash.sh $out <port>)"
