# Prebuilt ESP-IDF static libs + linker scripts + response files for
# arduino-esp32 3.3.10 (idf-release_v5.5-73550728-v6). The esp32c6 SDK dir is
# `esp32c6/` inside, containing lib/*.a, ld/, flags/{defines,includes,c_flags,
# cpp_flags,ld_flags,ld_scripts,ld_libs}, and a frozen sdkconfig. Treated
# read-only (a custom sdkconfig would require the full IDF build).
#
# TODO(build): replace fakeHash; confirm stripRoot (whether the zip has a single
# top-level dir) after the first fetch.
pkgs:
pkgs.fetchzip {
  url = "https://github.com/espressif/esp32-arduino-lib-builder/releases/download/idf-release_v5.5/esp32-arduino-libs-idf-release_v5.5-73550728-v6.zip";
  hash = "sha256-XQ19/tVQboqvTOKKi7c657pwBSGAdRA6nfQdeXQAujQ=";
  stripRoot = false;
}
