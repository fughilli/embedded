# BUILD for the @xtensa_gcc external repo (Espressif xtensa-esp-elf GCC).
# Mirrors nix/riscv_gcc.BUILD, but uses the per-chip xtensa-esp32-elf-* wrapper
# binaries: the unified toolchain selects the chip via -mdynconfig, and the
# esp32 wrappers bake in -mdynconfig=xtensa_esp32.so (matching arduino-esp32's
# compiler.prefix={build.tarch}-{build.target}-elf-).
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

[
    filegroup(
        name = tool,
        srcs = ["bin/xtensa-esp32-elf-%s" % tool],
    )
    for tool in [
        "gcc",
        "g++",
        "ar",
        "objcopy",
        "objdump",
        "strip",
        "nm",
        "size",
        "gcc-ranlib",
    ]
]
