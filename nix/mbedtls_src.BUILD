# Build mbedtls 3.6.5 (+ ESP-IDF v5.5.4 port) FROM SOURCE for the esp32c6, with
# CONFIG_MBEDTLS_DYNAMIC_BUFFER enabled. Replaces the prebuilt
# libmbedtls*/libmbedcrypto/libmbedx509 .a's (dropped from arduino_esp32.BUILD's
# :sdk_libs glob). Struct layout matches the precompiled libesp-tls.a /
# libesp_https_server.a because we compile against the SAME esp_config.h and only
# add DYNAMIC_BUFFER (a port knob, not a struct macro). Dynamic buffers are
# engaged via -Wl,--wrap of the 11 ssl functions (see :dynamic_wrap_linkopts),
# consumed by arduino_esp32.BUILD's :core.
#
# File selection transcribed from esp-idf v5.5.4 components/mbedtls/CMakeLists.txt
# for the C6 (SHA/AES via GDMA; HW MPI/SHA/AES/ECC; HMAC + DIG_SIGN on; LWIP on).
package(default_visibility = ["//visibility:public"])

_MBEDTLS_COPTS = [
    "-march=rv32imac_zicsr_zifencei",
    "-ffunction-sections",
    "-fdata-sections",
    "-fstrict-volatile-bitfields",
    "-fno-jump-tables",
    "-fno-tree-switch-conversion",
    "-std=gnu17",
    "-w",
    # Config: use the ESP port's mbedtls config; enable dynamic buffers. The
    # SDK's sdkconfig.h (on the include path via @arduino_esp32//:sdk_hdrs) does
    # not define CONFIG_MBEDTLS_DYNAMIC_BUFFER, so -D here is the only change.
    "-DMBEDTLS_CONFIG_FILE=\\\"mbedtls/esp_config.h\\\"",
    "-DCONFIG_MBEDTLS_DYNAMIC_BUFFER=1",
]

# mbedtls core (library/*.c) + 3rdparty ECC (everest, p256-m).
# Everest: compile ONLY the 3 files mbedtls' 3rdparty/everest/CMakeLists.txt
# lists. Hacl_Curve25519_joined.c #includes Hacl_Curve25519.c (and the
# kremlib/legacy .c files), so globbing library/*.c would double-define them.
_MBEDTLS_CORE = glob(
    [
        "mbedtls/library/*.c",
        "mbedtls/3rdparty/p256-m/**/p256-m.c",
    ],
    allow_empty = False,
) + [
    "mbedtls/3rdparty/everest/library/everest.c",
    "mbedtls/3rdparty/everest/library/x25519.c",
    "mbedtls/3rdparty/everest/library/Hacl_Curve25519_joined.c",
]

# ESP-IDF port sources selected for the C6.
_PORT_SRCS = [
    # base
    "port/mbedtls_debug.c",
    "port/esp_platform_time.c",
    "port/net_sockets.c",
    "port/esp_hardware.c",
    "port/esp_mem.c",
    "port/esp_timing.c",
    "port/esp_hmac_pbkdf2.c",
    # MD5 ROM implementation — MBEDTLS_MD5_ALT is set via CONFIG_MBEDTLS_ROM_MD5
    # in the SDK sdkconfig, so md.c/md5.c call esp_md5_* from here.
    "port/md/esp_md.c",
    # SHA (core / GDMA)
    "port/sha/esp_sha.c",
    "port/sha/core/sha.c",
    "port/sha/core/esp_sha_gdma_impl.c",
    "port/sha/core/esp_sha1.c",
    "port/sha/core/esp_sha256.c",
    "port/sha/core/esp_sha512.c",
    # AES (DMA / GDMA)
    "port/aes/esp_aes_common.c",
    "port/aes/esp_aes_xts.c",
    "port/aes/esp_aes_gcm.c",
    "port/aes/dma/esp_aes.c",
    "port/aes/dma/esp_aes_gdma_impl.c",
    "port/aes/dma/esp_aes_dma_core.c",
    # shared GDMA
    "port/crypto_shared_gdma/esp_crypto_shared_gdma.c",
    # MPI
    "port/bignum/esp_bignum.c",
    "port/bignum/bignum_alt.c",
    # ECC
    "port/ecc/esp_ecc.c",
    "port/ecc/ecc_alt.c",
    # Digital Signature peripheral (esp_ds)
    "port/esp_ds/esp_rsa_sign_alt.c",
    "port/esp_ds/esp_rsa_dec_alt.c",
    "port/esp_ds/esp_ds_common.c",
    # dynamic buffers — the feature
    "port/dynamic/esp_mbedtls_dynamic_impl.c",
    "port/dynamic/esp_ssl_cli.c",
    "port/dynamic/esp_ssl_srv.c",
    "port/dynamic/esp_ssl_tls.c",
]

cc_library(
    name = "mbedtls_src",
    srcs = _MBEDTLS_CORE + _PORT_SRCS,
    hdrs = glob([
        "mbedtls/include/**/*.h",
        "mbedtls/library/*.h",
        "mbedtls/3rdparty/**/*.h",
        "port/**/*.h",
    ]),
    # Port include dirs MUST precede mbedtls/include: the port ships wrapper
    # headers (e.g. mbedtls/bignum.h, mbedtls/gcm.h, mbedtls/ecp.h) that
    # `#include_next` the upstream ones to add ESP-only prototypes such as
    # mbedtls_mpi_exp_mod_soft. For #include_next to see the upstream header,
    # the port's mbedtls/ dir must come first on the -I search path.
    includes = [
        "port/include",
        "port/aes/include",
        "port/aes/dma/include",
        "port/sha/core/include",
        "mbedtls/include",
        "mbedtls/library",
        "mbedtls/3rdparty/everest/include",
        # everest sources #include "Hacl_Curve25519.h" / kremlib headers by
        # bare name; its CMakeLists adds these two as private include dirs.
        "mbedtls/3rdparty/everest/include/everest",
        "mbedtls/3rdparty/everest/include/everest/kremlib",
        "mbedtls/3rdparty/p256-m",
    ],
    copts = _MBEDTLS_COPTS,
    # Our symbols must satisfy the precompiled esp-tls/https_server callers.
    alwayslink = True,
    # esp_* / soc / hal / lwip / freertos headers the port pulls in.
    deps = ["@arduino_esp32//:sdk_hdrs"],
)

# The 11 --wrap flags that route the ssl entrypoints through the dynamic-buffer
# shims (__wrap_* live in port/dynamic/*.c; __real_* resolve from :mbedtls_src).
# arduino_esp32.BUILD's :core adds these to its linkopts.
DYNAMIC_WRAP_LINKOPTS = [
    "-Wl,--wrap=mbedtls_ssl_write_client_hello",
    "-Wl,--wrap=mbedtls_ssl_handshake_client_step",
    "-Wl,--wrap=mbedtls_ssl_tls13_handshake_client_step",
    "-Wl,--wrap=mbedtls_ssl_handshake_server_step",
    "-Wl,--wrap=mbedtls_ssl_read",
    "-Wl,--wrap=mbedtls_ssl_write",
    "-Wl,--wrap=mbedtls_ssl_session_reset",
    "-Wl,--wrap=mbedtls_ssl_free",
    "-Wl,--wrap=mbedtls_ssl_setup",
    "-Wl,--wrap=mbedtls_ssl_send_alert_message",
    "-Wl,--wrap=mbedtls_ssl_close_notify",
]
