# rules_nixpkgs entry points for the ESP32-family inputs (nix_pkg.file selects
# an attr). arduino-esp32 is the merged core+SDK tree; riscv32-esp-elf /
# xtensa-esp-elf are the Espressif prebuilt GCCs (C6 and classic ESP32/WROOM
# respectively). <nixpkgs> comes from the `repo = "@nixpkgs"` mapping.
let
  pkgs = import <nixpkgs> { };
in
{
  arduino-esp32 = import ./arduino_esp32_drv.nix pkgs;
  riscv32-esp-elf = import ./esp_riscv_gcc.nix pkgs;
  xtensa-esp-elf = import ./esp_xtensa_gcc.nix pkgs;
}
