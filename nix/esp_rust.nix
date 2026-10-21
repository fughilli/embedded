# esp-rs Rust toolchain: the rustc fork with Espressif's Xtensa LLVM backend
# (upstream rustc has no Xtensa target), plus a prebuilt no_std sysroot
# (core + compiler_builtins) for the classic ESP32, xtensa-esp32-none-elf.
#
# esp-rs ships no prebuilt rust-std for Xtensa targets — it expects cargo
# -Zbuild-std, which rules_rust doesn't do. So the sysroot is built here, once,
# offline, from pinned sources: the toolchain's own rust-src plus the
# compiler_builtins version its library/Cargo.lock pins (checksum from that
# lock). The rustc flags and compiler_builtins cfgs replay what
# `cargo -Zbuild-std=core --target xtensa-esp32-none-elf` runs (its build
# script turns on mem, f16/f128, unstable and force-soft-floats here).
#
# Version tracks the firmware module's upstream Rust (1.85.0) so crates that
# build for the other boards build here too.
# TODO(build): fill in the x86_64-linux / aarch64-darwin hashes on first use.
pkgs:
let
  version = "1.85.0.0";
  hosts = {
    aarch64-linux = {
      triple = "aarch64-unknown-linux-gnu";
      sha256 = "20a71a4dd5642a5fa132ee1442197fb72c52e692ab0e641c3420c6258fca1dd7";
    };
    x86_64-linux = {
      triple = "x86_64-unknown-linux-gnu";
      hash = pkgs.lib.fakeHash;
    };
    aarch64-darwin = {
      triple = "aarch64-apple-darwin";
      hash = pkgs.lib.fakeHash;
    };
  };
  host = hosts.${pkgs.stdenv.hostPlatform.system}
    or (throw "esp-rust: unsupported host system ${pkgs.stdenv.hostPlatform.system}");
  release = "https://github.com/esp-rs/rust-build/releases/download/v${version}";

  toolchain = pkgs.fetchurl ({
    url = "${release}/rust-${version}-${host.triple}.tar.xz";
  } // (if host ? sha256 then { inherit (host) sha256; } else { inherit (host) hash; }));
  rustSrc = pkgs.fetchurl {
    url = "${release}/rust-src-${version}.tar.xz";
    sha256 = "867155a0cee4fbd89f40d9012a77d0989544463234d6512577d99e16c1870872";
  };
  compilerBuiltinsVersion = "0.1.140";
  compilerBuiltins = pkgs.fetchurl {
    name = "compiler_builtins-${compilerBuiltinsVersion}.tar.gz";
    url = "https://crates.io/api/v1/crates/compiler_builtins/${compilerBuiltinsVersion}/download";
    sha256 = "df14d41c5d172a886df3753d54238eefb0f61c96cbd8b363c33ccc92c457bee3";
  };

  # Sysroot targets. Add esp32s2/esp32s3 here when a board needs them.
  targets = [ "xtensa-esp32-none-elf" ];
in
pkgs.stdenv.mkDerivation {
  pname = "esp-rust";
  inherit version;

  srcs = [ toolchain rustSrc compilerBuiltins ];
  sourceRoot = ".";

  nativeBuildInputs =
    pkgs.lib.optionals pkgs.stdenv.isLinux [ pkgs.autoPatchelfHook ];
  buildInputs =
    pkgs.lib.optionals pkgs.stdenv.isLinux [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];

  dontConfigure = true;
  dontBuild = true;
  dontStrip = true; # don't strip the compiler / sysroot

  installPhase = ''
    runHook preInstall
    patchShebangs rust-nightly-${host.triple}/install.sh rust-src-nightly/install.sh
    rust-nightly-${host.triple}/install.sh --prefix=$out --components=rustc \
      --disable-ldconfig > /dev/null
    rust-src-nightly/install.sh --prefix=$out --disable-ldconfig > /dev/null
    # rustc must run before fixup to build the sysroot: patch it now.
    ${pkgs.lib.optionalString pkgs.stdenv.isLinux "autoPatchelf $out"}

    library=$out/lib/rustlib/src/rust/library
    for target in ${pkgs.lib.concatStringsSep " " targets}; do
      sysroot=$out/lib/rustlib/$target/lib
      mkdir -p $sysroot
      common="--target $target --edition 2021 --crate-type lib \
        -Copt-level=3 -Cpanic=abort -Cembed-bitcode=no -Cstrip=debuginfo \
        -Zforce-unstable-if-unmarked --cap-lints allow \
        -Cmetadata=esp-rs -Cextra-filename=-esp --out-dir $sysroot"
      $out/bin/rustc --crate-name core $common $library/core/src/lib.rs
      $out/bin/rustc --crate-name compiler_builtins $common \
        --extern core=$sysroot/libcore-esp.rlib \
        --cfg 'feature="compiler-builtins"' --cfg 'feature="core"' \
        --cfg 'feature="default"' --cfg 'feature="rustc-dep-of-std"' \
        --cfg f16_enabled --cfg f128_enabled --cfg 'feature="unstable"' \
        --cfg 'feature="force-soft-floats"' --cfg 'feature="mem"' \
        compiler_builtins-${compilerBuiltinsVersion}/src/lib.rs
    done
    runHook postInstall
  '';
}
