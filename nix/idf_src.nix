# ESP-IDF v5.5.4 component sources: the IDF the prebuilt esp32-arduino-libs SDK was
# built from (versions.txt: esp-idf v5.5.4 735507283d; same pin as mbedtls_src.nix).
# For rebuilding single components FROM SOURCE against an sdkconfig overlay
# (arduino_esp32.BUILD "sdkconfig overrides"): the prebuilt archives keep the frozen
# sdkconfig, so an option that changes compiled code only takes effect in the
# components rebuilt here. Only the components with a from-source build are copied.
let
  pkgs = import <nixpkgs> { };
  idf = pkgs.fetchFromGitHub {
    owner = "espressif";
    repo = "esp-idf";
    rev = "v5.5.4";
    hash = "sha256-6p+4DO2/KjOel+vLQbbJH7xFNIYAwymKbxepQx3towI=";
  };
in
{
  idf-src = pkgs.runCommand "idf-src" { } ''
    mkdir -p $out/components
    cp -r ${idf}/components/esp_psram $out/components/esp_psram
    chmod -R u+w $out
    mkdir -p $out/glue
    cp ${./idf_glue/esp_psram_ext_bss_init.c} $out/glue/esp_psram_ext_bss_init.c
  '';
}
