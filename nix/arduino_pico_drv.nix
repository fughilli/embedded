# The arduino-pico source tree (earlephilhower core), fetched with submodules so
# the bundled pico-sdk headers and prebuilt libs (lib/rp2350/libpico.a,
# memmap_default.ld, ...) are present. Factored as a `pkgs -> derivation`
# function so both flake.nix and nix/arduino_pico.nix (rules_nixpkgs) can reuse
# it without duplicating the pin.
#
# The upstream tree (pico-sdk especially) ships its OWN Bazel BUILD.bazel files.
# Those turn pico-sdk into nested Bazel packages, which stops our single
# cc_library's glob from reaching the SDK headers. We strip every Bazel package
# marker so the whole tree is one package our generated BUILD owns. This wraps
# the fixed-output fetch in a plain derivation, so the FOD hash is unchanged.
pkgs:
let
  src = pkgs.fetchFromGitHub {
    owner = "earlephilhower";
    repo = "arduino-pico";
    rev = "5.6.1"; # latest stable tag as of 2026-07-10
    fetchSubmodules = true;
    hash = "sha256-Ul+Ft9Gewkiio/Y28ECycfF3TfVUUt6fezbjcNMLykw=";
  };
in
pkgs.runCommand "arduino-pico-5.6.1" { } ''
  cp -r --no-preserve=mode,ownership ${src} $out
  find $out \( \
      -name BUILD -o -name BUILD.bazel \
      -o -name WORKSPACE -o -name WORKSPACE.bazel \
      -o -name MODULE.bazel -o -name REPO.bazel \
    \) -delete
''
