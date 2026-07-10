# BUILD for the @arduino_pico external repo (Nix-fetched earlephilhower core).
#
# RP2350 (Arm Cortex-M33) only, so flags are fixed (no select()). The bare-metal
# -mcpu/-march/-mfloat-abi flags come from the cc_toolchain; here we add the
# Arduino/SDK includes, defines, prebuilt libs, and the exact link recipe.
#
# Includes/defines/link flags were transcribed from the repo's own
# lib/rp2350/platform_{inc,def,wrap}.txt, lib/core_{inc,wrap}.txt, boards.txt
# (rpipico2 stanza) and platform.txt (recipe.c.combine + compiler.ldflags).
# The big --wrap set is passed straight through via the shipped response files.
package(default_visibility = ["//visibility:public"])

# --- Prebuilt SDK artifacts (whole HAL: runtime, crt0, bootrom, hardware_*,
#     tinyusb, rp2350 xip_cache/sha256). We do NOT compile the SDK. -----------
filegroup(name = "libpico_a", srcs = ["lib/rp2350/libpico.a"])

filegroup(name = "liblwip_a", srcs = ["lib/rp2350/liblwip.a"])

filegroup(name = "libbearssl_a", srcs = ["lib/rp2350/libbearssl.a"])

filegroup(name = "ota_o", srcs = ["lib/rp2350/ota.o"])

# The shipped memmap_default.ld is a TEMPLATE; arduino-pico's simplesub.py
# prelink hook substitutes the memory-region sizes before linking. We replicate
# that with a genrule (values for rpipico2 / 4MB-no-FS / 512k RAM).
genrule(
    name = "memmap_ld",
    srcs = ["lib/rp2350/memmap_default.ld"],
    outs = ["memmap_default.gen.ld"],
    cmd = ("sed " +
           "-e 's/__FLASH_LENGTH__/4186112/g' " +
           "-e 's/__EEPROM_START__/272621568/g' " +
           "-e 's/__FS_START__/272621568/g' " +
           "-e 's/__FS_END__/272621568/g' " +
           "-e 's/__RAM_LENGTH__/512k/g' " +
           "-e 's/__PSRAM_LENGTH__/0/g' " +
           "$< > $@"),
)

# The shipped --wrap response files (math + memcpy → pico implementations).
filegroup(name = "wrap_platform", srcs = ["lib/rp2350/platform_wrap.txt"])

filegroup(name = "wrap_core", srcs = ["lib/core_wrap.txt"])

# --- Arduino core + Pico 2 variant + boot2 stub, compiled from source. ------
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
        exclude = [
            # sdkoverride/*.c #include SDK .c by relative path (wifi/BT/USB
            # overrides); not needed for blink and already inside libpico.a.
            "cores/rp2040/sdkoverride/**",
            # lwip/**/*.c are stubs that #include the SDK's lwip .c; networking
            # isn't needed for blink and liblwip.a is linked anyway.
            "cores/rp2040/lwip/**",
        ],
        allow_empty = True,
    ) + [
        "boot2/rp2350/none.S",  # build.boot2=none stub for rpipico2
        # Re-add the newlib syscall stubs (_sbrk/_write/_exit/...); standalone,
        # unlike the rest of sdkoverride which we exclude.
        "cores/rp2040/sdkoverride/newlib_interface.c",
    ],
    hdrs = glob(
        [
            "cores/rp2040/**/*.h",
            "variants/**/*.h",  # rpipico2/pins_arduino.h includes ../generic/common.h
            "pico-sdk/**/*.h",
            "include/**/*.h",
            "ArduinoCore-API/**/*.h",
            "FreeRTOS-Kernel/**/*.h",
        ],
        allow_empty = True,
    ),
    # cores/rp2040/api/*.cpp are thin wrappers that #include the real
    # ArduinoCore-API/api/*.cpp by relative path — stage those as textual (not
    # separately compiled) inputs.
    textual_hdrs = glob(
        [
            "ArduinoCore-API/**/*.cpp",
            "ArduinoCore-API/**/*.c",
        ],
        allow_empty = True,
    ),
    # From lib/rp2350/platform_inc.txt + lib/core_inc.txt (-iwithprefixbefore
    # paths) + the Arduino core/variant/include roots. Pruned to dirs present.
    includes = [
        "cores/rp2040",
        "variants/rpipico2",
        "include",
        "include/rp2350",
        "include/rp2350/pico_base",
        "pico-sdk/src/rp2350/hardware_regs/include",
        "pico-sdk/src/rp2350/hardware_structs/include",
        "pico-sdk/src/rp2350/pico_platform/include",
        "pico-sdk/src/rp2_common/cmsis/stub/CMSIS/Device/RP2350/Include",
        "pico-sdk/src/rp2_common/hardware_sha256/include",
        "pico-sdk/src/rp2_common/pico_sha256/include",
        "pico-sdk/src/rp2_common/pico_btstack/include",
        "pico-sdk/src/rp2_common/pico_cyw43_arch/include",
        "pico-sdk/src/rp2_common/pico_cyw43_driver/include",
        "pico-sdk/lib/cyw43-driver/src",
        "pico-sdk/lib/btstack/src",
        "pico-sdk/lib/btstack/3rd-party/bluedroid/decoder/include",
        "pico-sdk/lib/btstack/3rd-party/bluedroid/encoder/include",
        "pico-sdk/lib/btstack/3rd-party/yxml",
        "pico-sdk/lib/btstack/platform/embedded",
        "cores/rp2040/api/deprecated-avr-comp",
        "pico-sdk/lib/tinyusb/src",
        "pico-sdk/src/boards/include",
        "pico-sdk/src/common/hardware_claim/include",
        "pico-sdk/src/common/pico_base_headers/include",
        "pico-sdk/src/common/pico_binary_info/include",
        "pico-sdk/src/common/pico_sync/include",
        "pico-sdk/src/common/pico_time/include",
        "pico-sdk/src/common/pico_util/include",
        "pico-sdk/src/common/pico_stdlib_headers/include",
        "pico-sdk/src/common/pico_usb_reset_interface_headers/include",
        "pico-sdk/src/rp2_common/boot_bootrom_headers/include",
        "pico-sdk/src/rp2_common/cmsis/include",
        "pico-sdk/src/rp2_common/cmsis/stub/CMSIS/Core/Include",
        "pico-sdk/src/rp2_common/hardware_adc/include",
        "pico-sdk/src/rp2_common/hardware_base/include",
        "pico-sdk/src/rp2_common/hardware_boot_lock/include",
        "pico-sdk/src/rp2_common/hardware_clocks/include",
        "pico-sdk/src/rp2_common/hardware_divider/include",
        "pico-sdk/src/rp2_common/hardware_dma/include",
        "pico-sdk/src/rp2_common/hardware_exception/include",
        "pico-sdk/src/rp2_common/hardware_flash/include",
        "pico-sdk/src/rp2_common/hardware_gpio/include",
        "pico-sdk/src/rp2_common/hardware_i2c/include",
        "pico-sdk/src/rp2_common/hardware_interp/include",
        "pico-sdk/src/rp2_common/hardware_irq/include",
        "pico-sdk/src/rp2_common/hardware_rtc/include",
        "pico-sdk/src/rp2_common/hardware_pio/include",
        "pico-sdk/src/rp2_common/hardware_pll/include",
        "pico-sdk/src/rp2_common/hardware_powman/include",
        "pico-sdk/src/rp2_common/hardware_pwm/include",
        "pico-sdk/src/rp2_common/hardware_resets/include",
        "pico-sdk/src/rp2_common/hardware_spi/include",
        "pico-sdk/src/rp2_common/hardware_sync/include",
        "pico-sdk/src/rp2_common/hardware_sync_spin_lock/include",
        "pico-sdk/src/rp2_common/hardware_timer/include",
        "pico-sdk/src/rp2_common/hardware_uart/include",
        "pico-sdk/src/rp2_common/hardware_vreg/include",
        "pico-sdk/src/rp2_common/hardware_watchdog/include",
        "pico-sdk/src/rp2_common/hardware_xosc/include",
        "pico-sdk/src/rp2_common/pico_aon_timer/include",
        "pico-sdk/src/rp2_common/pico_async_context/include",
        "pico-sdk/src/rp2_common/pico_bootrom/include",
        "pico-sdk/src/rp2_common/pico_double/include",
        "pico-sdk/src/rp2_common/pico_fix/rp2040_usb_device_enumeration/include",
        "pico-sdk/src/rp2_common/pico_flash/include",
        "pico-sdk/src/rp2_common/pico_float/include",
        "pico-sdk/src/rp2_common/pico_int64_ops/include",
        "pico-sdk/src/rp2_common/pico_lwip/include",
        "pico-sdk/src/rp2_common/pico_multicore/include",
        "pico-sdk/src/rp2_common/pico_platform_common/include",
        "pico-sdk/src/rp2_common/pico_platform_compiler/include",
        "pico-sdk/src/rp2_common/pico_platform_sections/include",
        "pico-sdk/src/rp2_common/pico_platform_panic/include",
        "pico-sdk/src/rp2_common/pico_printf/include",
        "pico-sdk/src/rp2_common/pico_runtime/include",
        "pico-sdk/src/rp2_common/pico_runtime_init/include",
        "pico-sdk/src/rp2_common/pico_rand/include",
        "pico-sdk/src/rp2_common/pico_stdio/include",
        "pico-sdk/src/rp2_common/pico_stdio_uart/include",
        "pico-sdk/src/rp2_common/pico_unique_id/include",
        "pico-sdk/lib/lwip/src/include",
        "cores/rp2040/freertos",
    ],
    # Full define set from lib/platform_def.txt + lib/rp2350/platform_def.txt +
    # boards.txt (rpipico2) + the recipe.*.pattern -D's. PICO_CYW43_ARCH_HEADER
    # satisfies cyw43_arch.h; __DYNAMIC_REENT__ makes newlib declare __getreent
    # (whose symbol libpico.a provides). Space-containing string defines
    # (USB_MANUFACTURER/PRODUCT) can't be single tokens → see copts below.
    defines = [
        "CFG_TUSB_MCU=OPT_MCU_RP2040",
        "CFG_TUSB_OS=OPT_OS_PICO",
        "CYW43_DEFAULT_PIN_WL_CLOCK=29u",
        "CYW43_DEFAULT_PIN_WL_CS=25u",
        "CYW43_DEFAULT_PIN_WL_DATA_IN=24u",
        "CYW43_DEFAULT_PIN_WL_DATA_OUT=24u",
        "CYW43_DEFAULT_PIN_WL_HOST_WAKE=24u",
        "CYW43_DEFAULT_PIN_WL_REG_ON=23u",
        "CYW43_PIN_WL_DYNAMIC=1",
        "CYW43_PIO_CLOCK_DIV_DYNAMIC=1",
        "CYW43_WARN=//",
        "LIB_BOOT_STAGE2_HEADERS=1",
        "LIB_PICO_AON_TIMER=1",
        "LIB_PICO_ATOMIC=1",
        "LIB_PICO_BIT_OPS=1",
        "LIB_PICO_BIT_OPS_PICO=1",
        "LIB_PICO_BOOTSEL_VIA_DOUBLE_RESET=1",
        "LIB_PICO_CLIB_INTERFACE=1",
        "LIB_PICO_CRT0=1",
        "LIB_PICO_CXX_OPTIONS=1",
        "LIB_PICO_DIVIDER=1",
        "LIB_PICO_DIVIDER_COMPILER=1",
        "LIB_PICO_DOUBLE=1",
        "LIB_PICO_FIX_RP2040_USB_DEVICE_ENUMERATION=1",
        "LIB_PICO_FLASH=1",
        "LIB_PICO_FLOAT=1",
        "LIB_PICO_FLOAT_PICO=1",
        "LIB_PICO_INT64_OPS=1",
        "LIB_PICO_INT64_OPS_COMPILER=1",
        "LIB_PICO_MALLOC=1",
        "LIB_PICO_MEM_OPS=1",
        "LIB_PICO_MEM_OPS_COMPILER=1",
        "LIB_PICO_MULTICORE=1",
        "LIB_PICO_NEWLIB_INTERFACE=1",
        "LIB_PICO_PLATFORM=1",
        "LIB_PICO_PLATFORM_COMMON=1",
        "LIB_PICO_PLATFORM_COMPILER=1",
        "LIB_PICO_PLATFORM_PANIC=1",
        "LIB_PICO_PLATFORM_SECTIONS=1",
        "LIB_PICO_PRINTF=1",
        "LIB_PICO_PRINTF_PICO=1",
        "LIB_PICO_RAND=1",
        "LIB_PICO_RUNTIME=1",
        "LIB_PICO_RUNTIME_INIT=1",
        "LIB_PICO_STANDARD_BINARY_INFO=1",
        "LIB_PICO_STANDARD_LINK=1",
        "LIB_PICO_STDIO=0",
        "LIB_PICO_STDIO_UART=0",
        "LIB_PICO_STDLIB=1",
        "LIB_PICO_SYNC=1",
        "LIB_PICO_SYNC_CRITICAL_SECTION=1",
        "LIB_PICO_SYNC_MUTEX=1",
        "LIB_PICO_SYNC_SEM=1",
        "LIB_PICO_TIME=1",
        "LIB_PICO_TIME_ADAPTER=1",
        "LIB_PICO_UNIQUE_ID=1",
        "LIB_PICO_UTIL=1",
        "LIB_TINYUSB_BOARD=1",
        "LIB_TINYUSB_DEVICE=1",
        "PICO_32BIT=1",
        "PICO_BUILD=1",
        "PICO_COPY_TO_RAM=0",
        "PICO_NO_BINARY_INFO=1",
        "PICO_NO_FLASH=0",
        "PICO_NO_HARDWARE=0",
        "PICO_ON_DEVICE=1",
        "PICO_RP2040_USB_DEVICE_ENUMERATION_FIX=1",
        "PICO_RP2040_USB_DEVICE_UFRAME_FIX=1",
        "PICO_USE_BLOCKED_RAM=0",
        "PICO_XOSC_STARTUP_DELAY_MULTIPLIER=64",
        "PICO_MAX_SHARED_IRQ_HANDLERS=6",
        "PICO_CYW43_ARCH_HEADER=stdint.h",
        "CYW43_TASK_STACK_SIZE=1024",
        "LIB_PICO_DOUBLE_PICO=1",
        "LIB_PICO_FLOAT_PICO_VFP=1",
        "LIB_PICO_SHA256=1",
        "PICO_PLATFORM=rp2350-arm-s",
        "PICO_RP2350=1",
        "TARGET_RP2350",
        "F_CPU=125000000",
        "ARDUINO=10607",
        "ARDUINO_ARCH_RP2040",
        "ARDUINO_RASPBERRY_PI_PICO_2",
        'BOARD_NAME=\\"RASPBERRY_PI_PICO_2\\"',
        'ARDUINO_VARIANT=\\"rpipico2\\"',
        "USBD_VID=0x2e8a",
        "USBD_PID=0x000f",
        "USBD_MAX_POWER_MA=250",
        "PICO_FLASH_SIZE_BYTES=4194304",
        "FS_START=272621568",
        "FS_END=272621568",
        "__DYNAMIC_REENT__",
        # "No USB" mode: a headless blink doesn't need the USB device stack, and
        # compiling it out avoids libpico.a pulling in the tinyusb class drivers
        # (midid_*/hidd_*/mscd_*/netd_*).
        "NO_USB",
        "DISABLE_USB_SERIAL",
    ],
    # Space-containing USB descriptor strings — single-quote-wrapped so Bourne
    # tokenization keeps each as one token with the C-string quotes intact.
    copts = [
        "-DUSB_MANUFACTURER='\"Raspberry Pi\"'",
        "-DUSB_PRODUCT='\"Pico 2\"'",
    ],
    additional_linker_inputs = [
        ":libpico_a",
        ":liblwip_a",
        ":libbearssl_a",
        ":ota_o",
        ":memmap_ld",
        ":wrap_platform",
        ":wrap_core",
    ],
    # The link recipe (recipe.c.combine + compiler.ldflags), propagated to the
    # firmware binary. The prebuilt libs go in a --start-group (after Bazel's
    # objects) with -lm/-lc/-lstdc++ so the SDK's circular refs resolve.
    linkopts = [
        # --wrap sets (math + memcpy) via the shipped response files.
        "@$(location :wrap_platform)",
        "@$(location :wrap_core)",
        # compiler.ldflags (minus wrap): section GC + forced runtime-init syms.
        "-Wl,--cref",
        "-Wl,--check-sections",
        "-Wl,--gc-sections",
        "-Wl,--unresolved-symbols=report-all",
        "-Wl,--warn-common",
        "-Wl,--undefined=runtime_init_install_ram_vector_table",
        "-Wl,--undefined=__pre_init_runtime_init_clocks",
        "-Wl,--undefined=__pre_init_runtime_init_bootrom_reset",
        "-Wl,--undefined=__pre_init_runtime_init_early_resets",
        "-Wl,--undefined=__pre_init_runtime_init_usb_power_down",
        "-Wl,--undefined=__pre_init_runtime_init_post_clock_resets",
        "-Wl,--undefined=__pre_init_runtime_init_spin_locks_reset",
        "-Wl,--undefined=__pre_init_runtime_init_boot_locks_reset",
        "-Wl,--undefined=__pre_init_runtime_init_bootrom_locking_enable",
        "-Wl,--undefined=__pre_init_runtime_init_mutex",
        "-Wl,--undefined=__pre_init_runtime_init_default_alarm_pool",
        "-Wl,--undefined=__pre_init_first_per_core_initializer",
        "-Wl,--undefined=__pre_init_runtime_init_per_core_bootrom_reset",
        "-Wl,--undefined=__pre_init_runtime_init_per_core_h3_irq_registers",
        "-Wl,--undefined=__pre_init_runtime_init_per_core_irq_priorities",
        # Force newlib_interface.o (weak _sbrk/_write/... stubs) into the link
        # before libc references the syscalls — they all live in that one object.
        "-Wl,--undefined=_sbrk",
        "-Wl,--undefined=_write",
        "-Wl,--undefined=_read",
        "-Wl,--undefined=_exit",
        # Linker script + the group of prebuilt libs and system libs.
        "-Wl,--script=$(location :memmap_ld)",
        "-Wl,--no-warn-rwx-segments",
        "-Wl,--start-group",
        "$(location :ota_o)",
        "$(location :libpico_a)",
        "$(location :liblwip_a)",
        "$(location :libbearssl_a)",
        "-lm",
        "-lc",
        "-lstdc++",
        "-lc",
        "-Wl,--end-group",
    ],
)
