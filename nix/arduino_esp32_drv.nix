# arduino-esp32 core + the per-chip prebuilt SDKs (esp32-arduino-libs) merged
# into ONE tree so a single Bazel repo owns both — avoids cross-repo include/-L
# pain (the core sources and the SDK headers/libs/ld must resolve together).
# The SDKs land at sdk/<chip>/ (esp32c6 RISC-V, esp32 Xtensa LX6). Bazel
# package markers are stripped (same as arduino-pico).
pkgs:
let
  core = pkgs.fetchFromGitHub {
    owner = "espressif";
    repo = "arduino-esp32";
    rev = "3.3.10";
    hash = "sha256-C4yinBEB+J/RwRDPpE3lhQ65DcXicVNLJnynWhftPDc=";
  };
  libs = import ./esp32_arduino_libs.nix pkgs;
in
pkgs.runCommand "arduino-esp32-3.3.10" { } ''
  cp -r --no-preserve=mode,ownership ${core} $out
  mkdir -p $out/sdk
  cp -r --no-preserve=mode,ownership ${libs}/esp32-arduino-libs/esp32c6 $out/sdk/esp32c6
  cp -r --no-preserve=mode,ownership ${libs}/esp32-arduino-libs/esp32 $out/sdk/esp32
  find $out \( \
      -name BUILD -o -name BUILD.bazel \
      -o -name WORKSPACE -o -name WORKSPACE.bazel \
      -o -name MODULE.bazel -o -name REPO.bazel \
    \) -delete
''
