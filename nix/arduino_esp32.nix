# rules_nixpkgs entry points for the ESP32-C6 inputs (nix_pkg.file selects an
# attr). arduino-esp32 is the merged core+SDK tree; riscv32-esp-elf is the
# Espressif prebuilt GCC. <nixpkgs> comes from the `repo = "@nixpkgs"` mapping.
let
  pkgs = import <nixpkgs> { };
in
{
  arduino-esp32 = import ./arduino_esp32_drv.nix pkgs;
  riscv32-esp-elf = import ./esp_riscv_gcc.nix pkgs;
}
