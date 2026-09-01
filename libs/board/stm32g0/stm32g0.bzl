"""STM32G0 family helpers: per-part linker memory maps + pyOCD flash targets.

The whole G0 line shares one Cortex-M0+ cc_toolchain (//toolchains/cc/stm32g0)
and one set of bare-metal board support (//libs/board/stm32g0). A specific part
differs only in its Flash/SRAM sizes (the linker script) and its pyOCD target
name (flashing). Both live in the `STM32G0_VARIANTS` table below, so adding a
new part is a one-line entry; `stm32g0_linker_script` stamps its memory map from
the shared template.
"""

load("@bazel_skylib//rules:expand_template.bzl", "expand_template")

# part -> (flash KiB, ram KiB, pyOCD target). Sizes are for the largest-Flash
# suffix of each line (Nucleo defaults); override flash_k/ram_k for a smaller
# suffix. pyOCD targets outside its built-ins need a one-time
# `bazel run //tools/pyocd -- pack install <target>`.
STM32G0_VARIANTS = {
    "stm32g031": struct(flash_k = 64, ram_k = 8, pyocd_target = "stm32g031xx"),
    "stm32g041": struct(flash_k = 64, ram_k = 8, pyocd_target = "stm32g041xx"),
    "stm32g051": struct(flash_k = 64, ram_k = 18, pyocd_target = "stm32g051xx"),
    "stm32g061": struct(flash_k = 64, ram_k = 18, pyocd_target = "stm32g061xx"),
    "stm32g070": struct(flash_k = 128, ram_k = 36, pyocd_target = "stm32g070xx"),
    "stm32g071": struct(flash_k = 128, ram_k = 36, pyocd_target = "stm32g071xx"),
    "stm32g081": struct(flash_k = 128, ram_k = 36, pyocd_target = "stm32g081xx"),
    # Category 5 (larger Flash/SRAM, more peripherals). pyOCD targets are
    # per-part (from the CMSIS pack), so pick the exact device: stm32g0b1 here is
    # the STM32G0B1RCT6 (256K Flash / 144K SRAM). Add a distinct entry for other
    # suffixes (e.g. stm32g0b1retx = 512K).
    "stm32g0b1": struct(flash_k = 256, ram_k = 144, pyocd_target = "stm32g0b1rctx"),
    "stm32g0c1": struct(flash_k = 512, ram_k = 144, pyocd_target = "stm32g0c1xx"),
}

def stm32g0_linker_script(name, flash_k, ram_k, template = "//libs/board/stm32g0:stm32g0.ld.tpl"):
    """Generate a G0 linker script with the given Flash/SRAM sizes (KiB)."""
    expand_template(
        name = name,
        template = template,
        out = name + ".ld",
        substitutions = {
            "@FLASH_K@": str(flash_k),
            "@RAM_K@": str(ram_k),
        },
    )
