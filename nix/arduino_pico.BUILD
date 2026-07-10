# BUILD for the @arduino_pico external repo (Nix-fetched earlephilhower core).
#
# This repo is RP2350-only, so flags are fixed (no select()). The bare-metal
# -mcpu/-march/-mfloat-abi flags come from the cc_toolchain; here we only add
# the Arduino/SDK include dirs, defines, prebuilt libs, and the link recipe.
#
# ── AUTHORITATIVE SOURCES to transcribe (do this on the Nix host, iterating
#    against real compiler errors — this is the main Milestone-1 work surface):
#      lib/rp2350/platform_inc.txt   -> the `includes` list below
#      lib/rp2350/platform_def.txt   -> the `defines` list below
#      lib/rp2350/platform_wrap.txt  -> the -Wl,--wrap=... linkopts below
#      boards.txt (rpipico2 stanza)  -> F_CPU, board defines, variant name
#    Cross-check against `arduino-cli compile --verbose` for a blink sketch.
package(default_visibility = ["//visibility:public"])

# --- Prebuilt SDK libraries (the whole HAL: runtime, crt0, bootrom, hardware_*,
#     tinyusb, rp2350 xip_cache/sha256). We do NOT compile the SDK. -----------
cc_import(
    name = "libpico",
    static_library = "lib/rp2350/libpico.a",
)

cc_import(
    name = "liblwip",
    static_library = "lib/rp2350/liblwip.a",
)

cc_import(
    name = "libbearssl",
    static_library = "lib/rp2350/libbearssl.a",
)

# --- Linker script shipped alongside the prebuilt libs. --------------------
filegroup(
    name = "memmap_ld",
    srcs = ["lib/rp2350/memmap_default.ld"],
)

# --- Arduino core + Pico 2 variant, compiled from source. ------------------
# NOTE: the include list is a STARTER set. Replace/extend from platform_inc.txt.
cc_library(
    name = "core",
    srcs = glob(
        [
            "cores/rp2040/**/*.c",
            "cores/rp2040/**/*.cpp",
            "cores/rp2040/**/*.S",
            "variants/rpipico2/**/*.c",
            "variants/rpipico2/**/*.cpp",
            "variants/rpipico2/**/*.S",
        ],
        allow_empty = True,
    ),
    hdrs = glob(
        [
            "cores/rp2040/**/*.h",
            "variants/rpipico2/**/*.h",
            "pico-sdk/**/*.h",
            "include/**/*.h",
        ],
        allow_empty = True,
    ),
    # Starter include roots — extend from platform_inc.txt (there are many
    # pico-sdk/src/**/include dirs).
    includes = [
        "cores/rp2040",
        "variants/rpipico2",
        "include",
        "pico-sdk/src/common/pico_base_headers/include",
        "pico-sdk/src/common/pico_stdlib_headers/include",
        "pico-sdk/src/rp2_common/hardware_gpio/include",
        "pico-sdk/src/rp2_common/pico_platform/include",
    ],
    # Starter defines — extend from platform_def.txt / boards.txt.
    defines = [
        "ARDUINO=10607",
        "ARDUINO_ARCH_RP2040",
        "ARDUINO_RASPBERRY_PI_PICO_2",
        'BOARD_NAME=\\"Raspberry Pi Pico 2\\"',
        "F_CPU=150000000",
        "PICO_RP2350=1",
    ],
    # Link recipe propagated to the firmware binary. Transcribe the full
    # --wrap set from platform_wrap.txt; a few representative ones shown.
    additional_linker_inputs = [":memmap_ld"],
    linkopts = [
        "-Wl,-T,$(location :memmap_ld)",
        "--specs=nano.specs",
        "-Wl,--gc-sections",
        # From platform_wrap.txt (extend to the full list):
        "-Wl,--wrap=malloc",
        "-Wl,--wrap=calloc",
        "-Wl,--wrap=free",
        "-Wl,--wrap=printf",
    ],
    deps = [
        ":libpico",
        ":liblwip",
        ":libbearssl",
    ],
)
