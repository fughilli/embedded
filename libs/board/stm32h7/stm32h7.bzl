"""STM32H7 helpers: per-part linker memory maps + pyOCD flash targets.

Single-M7-side view of the STM32H757 (Cube Orange+ autopilot MCU). Like the
STM32G0 line, the family shares one Cortex-M7 cc_toolchain (//toolchains/cc/stm32h7)
and one set of bare-metal board support (//libs/board/stm32h7); a specific part
differs only in its Flash/SRAM sizes (the linker script) and its pyOCD target
name (flashing). `stm32h7_linker_script` stamps the memory map from the shared
template.
"""

load("@bazel_skylib//rules:expand_template.bzl", "expand_template")

# part -> (flash KiB, ram KiB, pyOCD target). ram_k is the D1-domain AXI-SRAM
# (0x24000000, 512K) used by the linker script; the H757 also has DTCM/other SRAM
# banks not modelled here. flash_k is the full 2MB dual-bank Flash at 0x08000000.
# pyOCD targets outside its built-ins need a one-time
# `bazel run //tools/pyocd -- pack install <target>`.
STM32H7_VARIANTS = {
    "stm32h757": struct(flash_k = 2048, ram_k = 512, pyocd_target = "stm32h757ziyx"),
}

def stm32h7_linker_script(name, flash_k, ram_k, template = "//libs/board/stm32h7:stm32h7.ld.tpl"):
    """Generate an H7 linker script with the given Flash/AXI-SRAM sizes (KiB)."""
    expand_template(
        name = name,
        template = template,
        out = name + ".ld",
        substitutions = {
            "@FLASH_K@": str(flash_k),
            "@RAM_K@": str(ram_k),
        },
    )
