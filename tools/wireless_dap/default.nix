# Patched source of the wireless ESP32 CMSIS-DAP firmware (kerms/wireless-esp32-tools),
# pinned to the revision the patches were made against. Build it with ./build.sh.
#   nix build .#wireless-dap-src      (from the repo root)
{ applyPatches, fetchFromGitHub }:
applyPatches {
  name = "wireless-esp32-tools-src";
  src = fetchFromGitHub {
    owner = "kerms";
    repo = "wireless-esp32-tools";
    rev = "6a625c0c5791068e020ce18c4c0090db6d0321b6";
    hash = "sha256-0vG4ZSfJhUR1tegZpeZQpMasjDZ5FQXT1klaKiyg8ho=";
  };
  patches = [
    ./patches/0001-Add-a-serial-console-for-Wi-Fi-provisioning.patch
    ./patches/0002-Fix-bit-banged-SWD-on-the-classic-ESP32.patch
    ./patches/0003-Pin-managed-components-espressif-mdns-with-dependenc.patch
  ];
}
