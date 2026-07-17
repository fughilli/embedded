# Espressif prebuilt xtensa-esp-elf GCC (matches arduino-esp32 3.3.10's pinned
# toolchain esp-14.2.0_20260121) — the Xtensa LX6/LX7 counterpart of
# esp_riscv_gcc.nix, for the classic ESP32 (WROOM) / S2 / S3. One unified
# toolchain covers all Xtensa chips; the multilib is picked by -mcpu / the
# per-chip flags response files.
#
# Tarball is selected by host platform; macOS Mach-O binaries need no patching.
# TODO(build): fill in the x86_64-linux / aarch64-darwin hashes on first use
# (`nix store prefetch-file <url>`).
pkgs:
let
  version = "14.2.0_20260121";
  srcs = {
    aarch64-linux = {
      triple = "aarch64-linux-gnu";
      hash = "sha256-8v23KwICkWNAYzYk6+zRMPCIsmUMCuKlBxWVIR0kyro=";
    };
    x86_64-linux = {
      triple = "x86_64-linux-gnu";
      hash = pkgs.lib.fakeHash;
    };
    aarch64-darwin = {
      triple = "aarch64-apple-darwin";
      hash = pkgs.lib.fakeHash;
    };
  };
  src = srcs.${pkgs.stdenv.hostPlatform.system}
    or (throw "xtensa-esp-elf: unsupported host system ${pkgs.stdenv.hostPlatform.system}");
in
pkgs.stdenv.mkDerivation {
  pname = "xtensa-esp-elf";
  inherit version;

  src = pkgs.fetchurl {
    url = "https://github.com/espressif/crosstool-NG/releases/download/esp-${version}/xtensa-esp-elf-${version}-${src.triple}.tar.gz";
    hash = src.hash;
  };

  # The tarball's top dir is xtensa-esp-elf/, so after unpack $PWD is that dir
  # and its contents (bin/, xtensa-esp-elf/, lib/, ...) go straight to $out.
  nativeBuildInputs =
    pkgs.lib.optionals pkgs.stdenv.isLinux [ pkgs.autoPatchelfHook ];
  buildInputs =
    pkgs.lib.optionals pkgs.stdenv.isLinux [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];

  dontConfigure = true;
  dontBuild = true;
  dontStrip = true; # don't strip the cross toolchain
  # Scripts in libexec reference build-machine shells; harmless for our use and
  # patching them on darwin rewrites nothing useful.
  dontPatchShebangs = pkgs.stdenv.isDarwin;

  installPhase = ''
    mkdir -p $out
    cp -r ./* $out/
  '';
}
