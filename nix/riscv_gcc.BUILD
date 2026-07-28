# BUILD for the @riscv_gcc external repo (Espressif riscv32-esp-elf GCC).
# Tools are prefixed riscv32-esp-elf-. Mirrors nix/arm_gcc.BUILD.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

[
    filegroup(
        name = tool,
        srcs = ["bin/riscv32-esp-elf-%s" % tool],
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
