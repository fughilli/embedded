# ESP-IDF components built FROM SOURCE against the sdkconfig overlay (see
# arduino_esp32.BUILD "sdkconfig overrides"), each replacing its prebuilt archive's
# objects: linked always (ahead of the SDK's --start-group), so the archive member
# with the same symbols is never pulled.
package(default_visibility = ["//visibility:public"])

_C_COPTS_ESP32P4 = [
    "-march=rv32imafc_zicsr_zifencei_xesploop_xespv",
    "-mabi=ilp32f",
    "-ffunction-sections",
    "-fdata-sections",
    "-fstrict-volatile-bitfields",
    "-fno-jump-tables",
    "-fno-tree-switch-conversion",
    "-std=gnu17",
    "-w",
]

# esp_psram's system layer (components/esp_psram/CMakeLists.txt: system_layer/esp_psram.c
# whenever SPIRAM is on): the PSRAM heap, .ext_ram.bss (CONFIG_SPIRAM_ALLOW_BSS_SEG_
# EXTERNAL_MEMORY: reserved out of the heap and zeroed at boot), noinit and XIP.
cc_library(
    name = "esp_psram_esp32p4",
    srcs = [
        "components/esp_psram/system_layer/esp_psram.c",
        "glue/esp_psram_ext_bss_init.c",
    ],
    hdrs = glob([
        "components/esp_psram/device/include/**/*.h",
        "components/esp_psram/include/**/*.h",
    ]),
    copts = _C_COPTS_ESP32P4,
    includes = [
        "components/esp_psram/device/include",
        "components/esp_psram/include",
    ],
    alwayslink = True,
    implementation_deps = ["@arduino_esp32//:sdk_hdrs_esp32p4"],
)
