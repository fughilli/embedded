# Espressif prebuilt riscv32-esp-elf GCC (matches arduino-esp32 3.3.10's pinned
# toolchain esp-14.2.0_20260121). Fetched directly and (on Linux) autoPatchelf'd
# rather than via the nixpkgs-esp-dev flake (which drags in all of ESP-IDF).
#
# Tarball is selected by host platform; macOS Mach-O binaries need no patching.
# TODO(build): fill in the x86_64-linux hash on first use (`nix store
# prefetch-file <url>`).
pkgs:
let
  version = "14.2.0_20260121";
  srcs = {
    aarch64-linux = {
      triple = "aarch64-linux-gnu";
      hash = "sha256-lPNuupGR+MuFA86in9mond0yBSf7pe85YMi8aTVI1HE=";
    };
    x86_64-linux = {
      triple = "x86_64-linux-gnu";
      hash = pkgs.lib.fakeHash;
    };
    aarch64-darwin = {
      triple = "aarch64-apple-darwin";
      hash = "sha256-yzIzZFKkyJlrOIFHYalF/nhW+tofTVeVDLq+mw7L/FI=";
    };
  };
  src = srcs.${pkgs.stdenv.hostPlatform.system}
    or (throw "riscv32-esp-elf: unsupported host system ${pkgs.stdenv.hostPlatform.system}");
in
pkgs.stdenv.mkDerivation {
  pname = "riscv32-esp-elf";
  inherit version;

  src = pkgs.fetchurl {
    url = "https://github.com/espressif/crosstool-NG/releases/download/esp-${version}/riscv32-esp-elf-${version}-${src.triple}.tar.gz";
    hash = src.hash;
  };

  # The tarball's top dir is riscv32-esp-elf/, so after unpack $PWD is that dir
  # and its contents (bin/, riscv32-esp-elf/, lib/, ...) go straight to $out.
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
