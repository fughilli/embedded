"""`firmware_binary`: one macro that turns a board-agnostic firmware source into
all the per-board targets — ELF, flashable artifact, and a `flash` runner —
for both RP2350 and ESP32-C6.

Assumes ONE firmware_binary per package (it creates fixed short target names).
For `firmware_binary(name = "app", ...)` you get:

    :app                 cc_binary (board-agnostic ELF; only built via transition)
    :rp2350  :esp32c6    embedded_binary (retargeted to each board)
    :rp2350_uf2          RP2350 .uf2         :esp32c6_bin  ESP32-C6 app .bin
    :flash_rp2350        picotool load        :flash_esp32c6  esptool write-flash
"""

load("//rules:embedded.bzl", "embedded_binary")
load("//rules:flash.bzl", "esptool_flash", "picotool_flash")

def firmware_binary(name, srcs, deps = [], copts = [], **kwargs):
    # Board-agnostic ELF: the board core comes from deps (//libs/board or a lib
    # that depends on //libs/board:arduino_core). target_compatible_with makes it
    # a no-op off a board platform, so it's only built via embedded_binary.
    native.cc_binary(
        name = name,
        srcs = srcs,
        copts = copts,
        target_compatible_with = select({
            "//platforms:is_rp2350": [],
            "//platforms:is_esp32c6": [],
            "//conditions:default": ["@platforms//:incompatible"],
        }),
        deps = deps,
        **kwargs
    )

    # --- RP2350 (Arm) -> .uf2 via picotool ---
    embedded_binary(name = "rp2350", binary = ":" + name, platform = "//platforms:rp2350")
    native.genrule(
        name = "rp2350_uf2",
        srcs = [":rp2350"],
        outs = ["firmware_rp2350.uf2"],
        cmd = "$(execpath @picotool//:bin) uf2 convert $(location :rp2350) $@ --family rp2350-arm-s",
        tools = ["@picotool//:bin", "@picotool//:all"],
    )
    picotool_flash(name = "flash_rp2350", uf2 = ":rp2350_uf2")

    # --- ESP32-C6 (RISC-V) -> .bin via esptool ---
    embedded_binary(name = "esp32c6", binary = ":" + name, platform = "//platforms:esp32c6")
    _esp_elf2image("esp32c6_bin", ":esp32c6", "firmware_esp32c6.bin")
    _esp_elf2image("esp32c6_bootloader", "@arduino_esp32//:bootloader_elf", "bootloader.bin")
    esptool_flash(
        name = "flash_esp32c6",
        chip = "esp32c6",
        app = ":esp32c6_bin",
        bootloader = ":esp32c6_bootloader",
        partitions = "@arduino_esp32//:partitions_default",
        boot_app0 = "@arduino_esp32//:boot_app0",
    )

def _esp_elf2image(name, elf, out):
    native.genrule(
        name = name,
        srcs = [elf],
        outs = [out],
        cmd = ("$(execpath @esptool//:bin) --chip esp32c6 elf2image " +
               "--flash_mode qio --flash_freq 80m --flash_size 4MB " +
               "-o $@ $(location %s)" % elf),
        tools = ["@esptool//:bin", "@esptool//:all"],
    )
