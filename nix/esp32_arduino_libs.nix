# Prebuilt ESP-IDF static libs + linker scripts + response files for
# arduino-esp32 3.3.10 (idf-release_v5.5-73550728-v6). The esp32c6 SDK dir is
# `esp32c6/` inside, containing lib/*.a, ld/, flags/{defines,includes,c_flags,
# cpp_flags,ld_flags,ld_scripts,ld_libs}, and a frozen sdkconfig. Treated
# read-only (a custom sdkconfig would require the full IDF build).
#
# The upstream zip carries EVERY chip variant (esp32, s2/s3, c3/c5/c6/h2, p4);
# unpacked in full it is ~10 GB, which overflows a small container overlay. We
# build esp32c6 + esp32c3 ONLY, so fetch the raw zip and selectively unzip just
# the `esp32-arduino-libs/esp32c6/` and `.../esp32c3/` subtrees (~2-3 GB).
# `hash` is therefore the RAW ZIP's sha256 (fetchurl), NOT the unpacked-NAR hash
# that fetchzip used. esp32c3 is the build-only c3 target (RISC-V rv32imc); see
# //MODULE.bazel and the c3 firmware BUILD note.
pkgs:
let
  zip = pkgs.fetchurl {
    url = "https://github.com/espressif/esp32-arduino-lib-builder/releases/download/idf-release_v5.5/esp32-arduino-libs-idf-release_v5.5-73550728-v6.zip";
    hash = "sha256-bZI7vxfxbQlK3GtQNpe/kMzjBoVjUO6BXgh9VYL303o=";
  };
in
pkgs.runCommand "esp32-arduino-libs-c6-c3" { nativeBuildInputs = [ pkgs.unzip ]; } ''
  mkdir -p $out
  unzip -q ${zip} 'esp32-arduino-libs/esp32c6/*' 'esp32-arduino-libs/esp32c3/*' -d $out
''
