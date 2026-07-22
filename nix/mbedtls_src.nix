# mbedtls 3.6.5 (espressif fork) source + the ESP-IDF v5.5.4 mbedtls port,
# assembled into one tree so @embedded can build mbedtls FROM SOURCE with
# CONFIG_MBEDTLS_DYNAMIC_BUFFER on (lifts the ~2-concurrent-TLS-session cap on
# the C6). Pins match the prebuilt esp32-arduino-libs SDK exactly
# (versions.txt: esp-idf v5.5.4 735507283d; mbedtls submodule ffb280bb).
#
# The mbedtls .a's from the prebuilt SDK are dropped in arduino_esp32.BUILD and
# replaced by //:mbedtls_src built from this tree. All *headers* the port needs
# (soc/hal/esp_hw_support/…) already ship in the SDK include tree, so this
# derivation carries only mbedtls sources + the port .c/.h.
#
# Layout in $out:
#   mbedtls/{library,include,3rdparty}   (upstream mbedtls)
#   port/**                              (IDF components/mbedtls/port)
pkgs:
let
  mbedtls = pkgs.fetchFromGitHub {
    owner = "espressif";
    repo = "mbedtls";
    rev = "ffb280bb63c78bfec1e1ab55040671768c85c923";
    hash = "sha256-671VYuTxMOLF90UXnBofct5jBQZuBJUoBVueMP3vVUQ=";
  };
  # Only components/mbedtls/port is used; sparseCheckout keeps the fetch small.
  idf = pkgs.fetchFromGitHub {
    owner = "espressif";
    repo = "esp-idf";
    rev = "v5.5.4";
    hash = "sha256-6p+4DO2/KjOel+vLQbbJH7xFNIYAwymKbxepQx3towI=";
  };
in
{
  mbedtls-src = pkgs.runCommand "mbedtls-src" { } ''
    mkdir -p $out
    cp -r ${mbedtls} $out/mbedtls
    cp -r ${idf}/components/mbedtls/port $out/port
    chmod -R u+w $out
  '';
}
