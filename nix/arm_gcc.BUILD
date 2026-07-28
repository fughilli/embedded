# BUILD for the @arm_gcc external repo (Nix-provided gcc-arm-embedded 13.3).
# Exposes the tool binaries as labels so our cc_toolchain_config can reference
# them via `tool(tool = <File>)` (cross-repo-safe, unlike string tool_paths),
# plus an `all` filegroup that pulls the whole toolchain tree into the sandbox.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# Individual tools. The `bin/arm-none-eabi-*` symlinks come straight from the
# Nix output; if the package lays them out differently, adjust these globs.
[
    filegroup(
        name = tool,
        srcs = ["bin/arm-none-eabi-%s" % tool],
    )
    for tool in [
        "gcc",
        "g++",
        "ar",
        "ld",
        "objcopy",
        "objdump",
        "strip",
        "nm",
        "size",
        "gcc-ranlib",
    ]
]

# Convenience aggregates the cc_toolchain wires to its *_files attributes.
filegroup(
    name = "compiler_files",
    srcs = [":all"],
)

filegroup(
    name = "linker_files",
    srcs = [":all"],
)
