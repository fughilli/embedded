# Espressif prebuilt riscv32-esp-elf GCC (matches arduino-esp32 3.3.10's pinned
# toolchain esp-14.2.0_20260121). Fetched directly and autoPatchelf'd rather than
# via the nixpkgs-esp-dev flake (which drags in all of ESP-IDF). aarch64 host.
#
# TODO(build): replace fakeHash after the first `nix build`; if autoPatchelf
# reports missing libs, add them to buildInputs.
pkgs:
pkgs.stdenv.mkDerivation {
  pname = "riscv32-esp-elf";
  version = "14.2.0_20260121";

  src = pkgs.fetchurl {
    url = "https://github.com/espressif/crosstool-NG/releases/download/esp-14.2.0_20260121/riscv32-esp-elf-14.2.0_20260121-aarch64-linux-gnu.tar.gz";
    hash = "sha256-lPNuupGR+MuFA86in9mond0yBSf7pe85YMi8aTVI1HE=";
  };

  # The tarball's top dir is riscv32-esp-elf/, so after unpack $PWD is that dir
  # and its contents (bin/, riscv32-esp-elf/, lib/, ...) go straight to $out.
  nativeBuildInputs = [ pkgs.autoPatchelfHook ];
  buildInputs = [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];

  dontConfigure = true;
  dontBuild = true;
  dontStrip = true; # don't strip the cross toolchain

  installPhase = ''
    mkdir -p $out
    cp -r ./* $out/
  '';
}
