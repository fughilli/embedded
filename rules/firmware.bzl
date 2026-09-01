"""`firmware_binary`: build a board-agnostic `cc_binary` for a specific board
(via an outgoing platform transition) and package it into that board's flashable
artifact — a `.uf2` for RP2350 (picotool) or an app `.bin` for the ESP32 family
(esptool; boards `esp32c6` and `esp32`, the classic Xtensa WROOM chip).

This is a RULE, not a macro: every label it uses is either supplied by the
caller (`binary`) or a private-attr default that resolves in THIS module's repo
(`@picotool`, `@esptool`, `//platforms:*`). So it is reusable from other Bazel
modules with no caller-relative labels. Pair it with the flash rules in
`//rules:flash.bzl`:

    cc_binary(name = "app", srcs = ["app.cpp"], deps = [...],
              target_compatible_with = select({
                  "@firmware//platforms:is_rp2350": [],
                  "@firmware//platforms:is_esp32c6": [],
                  "//conditions:default": ["@platforms//:incompatible"]}))
    firmware_binary(name = "app_rp2350", binary = ":app", board = "rp2350")
    firmware_binary(name = "app_esp32c6", binary = ":app", board = "esp32c6")

The retargeted ELF is available via the `elf` output group.
"""

FirmwareInfo = provider(
    doc = "A built firmware artifact + the debug inputs a GDB session needs.",
    fields = {
        "elf": "The ELF File (symbols/sections — what GDB loads).",
        "image": "The flashable image File (.uf2 / .bin).",
        "board": "The board name it was built for.",
        "name": "The firmware target name.",
    },
)

# ---------------------------------------------------------------------------
# debug_elf: rebuild a firmware/stub ELF WITH debug info, for a GDB session.
# ---------------------------------------------------------------------------
# The flash build strips debug info (fastbuild default --strip=sometimes) and
# doesn't compile with -g. For debugging we transition the ELF to --strip=never
# and add -ggdb3 to the compile, without touching the normal build (the flashed
# image is unaffected — it comes from the stripped path).
def _debug_cfg_impl(settings, _attr):
    return {
        "//command_line_option:strip": "never",
        "//command_line_option:copt": settings["//command_line_option:copt"] + ["-ggdb3"],
    }

_debug_cfg = transition(
    implementation = _debug_cfg_impl,
    inputs = ["//command_line_option:copt"],
    outputs = ["//command_line_option:strip", "//command_line_option:copt"],
)

def _debug_elf_impl(ctx):
    dep = ctx.attr.firmware[0]  # transitioned -> 1-element list
    if ctx.attr.output_group:
        elf = getattr(dep[OutputGroupInfo], ctx.attr.output_group).to_list()[0]
    else:
        elf = dep[DefaultInfo].files.to_list()[0]
    out = ctx.actions.declare_file(ctx.label.name + ".elf")
    ctx.actions.symlink(output = out, target_file = elf)
    return [DefaultInfo(files = depset([out]))]

debug_elf = rule(
    implementation = _debug_elf_impl,
    doc = "Republish a firmware/stub ELF rebuilt with debug info (--strip=never " +
          "+ -ggdb3) for a GDB session.",
    attrs = {
        "firmware": attr.label(mandatory = True, cfg = _debug_cfg),
        "output_group": attr.string(
            doc = "Output group holding the ELF (e.g. `elf` for firmware_binary); " +
                  "empty = the target's default output (e.g. a simulation_stub).",
        ),
        "_allowlist_function_transition": attr.label(
            default = "@bazel_tools//tools/allowlists/function_transition_allowlist",
        ),
    },
)

# Board -> platform, resolved in THIS module's repo (so the transition targets
# @firmware//platforms:* even when the rule is used from another module).
_BOARD_PLATFORM = {
    "rp2350": Label("//platforms:rp2350"),
    "esp32c6": Label("//platforms:esp32c6"),
    "esp32": Label("//platforms:esp32"),
    "stm32g0": Label("//platforms:stm32g0"),
}

def _board_transition_impl(settings, attr):
    return {
        "//command_line_option:platforms": [str(_BOARD_PLATFORM[attr.board])],
        "//command_line_option:compilation_mode": attr.opt_mode or settings["//command_line_option:compilation_mode"],
    }

_board_transition = transition(
    implementation = _board_transition_impl,
    inputs = ["//command_line_option:compilation_mode"],
    outputs = [
        "//command_line_option:platforms",
        "//command_line_option:compilation_mode",
    ],
)

def _firmware_binary_impl(ctx):
    # `binary` is transitioned, so ctx.attr.binary is a 1-element list. The
    # cc_binary output has no extension; picotool needs a `.elf` to detect the
    # input type, so republish it under a `.elf` name.
    elf = ctx.actions.declare_file(ctx.label.name + ".elf")
    ctx.actions.symlink(
        output = elf,
        target_file = ctx.attr.binary[0][DefaultInfo].files_to_run.executable,
    )
    board = ctx.attr.board

    args = ctx.actions.args()
    if board == "rp2350":
        out = ctx.actions.declare_file(ctx.label.name + ".uf2")
        tool = ctx.file._picotool
        tool_files = ctx.attr._picotool_files[DefaultInfo].files
        args.add("uf2")
        args.add("convert")
        args.add(elf)
        args.add(out)
        args.add("--family", "rp2350-arm-s")
    elif board == "stm32g0":
        # Bare-metal STM32: strip the ELF to a raw Flash image. Flashes at the
        # Flash origin 0x08000000 (pyOCD / st-flash / dfu-util). objcopy comes
        # from the same @arm_gcc as the compiler.
        out = ctx.actions.declare_file(ctx.label.name + ".bin")
        tool = ctx.file._objcopy
        tool_files = ctx.attr._arm_gcc_files[DefaultInfo].files
        args.add("-O", "binary")
        args.add(elf)
        args.add(out)
    else:  # esp32 family — the board name IS the esptool chip name
        out = ctx.actions.declare_file(ctx.label.name + ".bin")
        tool = ctx.file._esptool
        tool_files = ctx.attr._esptool_files[DefaultInfo].files
        args.add("--chip", board)
        args.add("elf2image")
        args.add("--flash_mode", ctx.attr.flash_mode)
        args.add("--flash_freq", ctx.attr.flash_freq)
        args.add("--flash_size", ctx.attr.flash_size)
        args.add("-o", out)
        args.add(elf)

    ctx.actions.run(
        executable = tool,
        arguments = [args],
        inputs = depset([elf]),
        tools = [tool_files],
        outputs = [out],
        mnemonic = "FirmwareImage",
        progress_message = "Packaging %{label}",
    )
    return [
        DefaultInfo(files = depset([out])),
        OutputGroupInfo(elf = depset([elf])),
        FirmwareInfo(elf = elf, image = out, board = board, name = ctx.label.name),
    ]

firmware_binary = rule(
    implementation = _firmware_binary_impl,
    doc = "Build `binary` for `board` and package its flashable artifact.",
    attrs = {
        "binary": attr.label(
            mandatory = True,
            cfg = _board_transition,
            doc = "The board-agnostic cc_binary to build + package.",
        ),
        "board": attr.string(
            mandatory = True,
            values = ["rp2350", "esp32c6", "esp32", "stm32g0"],
            doc = "Which board to build for (drives the transition + packager).",
        ),
        "opt_mode": attr.string(
            values = ["", "fastbuild", "dbg", "opt"],
            doc = "Compilation mode for the transitioned binary; empty = " +
                  "inherit the command-line -c setting.",
        ),
        # DIO in the image header even on QIO boards — the ROM boots in DIO and
        # firmware upgrades to quad I/O itself (matches arduino-esp32).
        "flash_mode": attr.string(default = "dio"),
        "flash_freq": attr.string(default = "80m"),
        "flash_size": attr.string(default = "4MB"),
        "_picotool": attr.label(
            default = "@picotool//:bin",
            allow_single_file = True,
            cfg = "exec",
        ),
        "_picotool_files": attr.label(default = "@picotool//:all", cfg = "exec"),
        "_esptool": attr.label(
            default = "@esptool//:bin",
            allow_single_file = True,
            cfg = "exec",
        ),
        "_esptool_files": attr.label(default = "@esptool//:all", cfg = "exec"),
        "_objcopy": attr.label(
            default = "@arm_gcc//:objcopy",
            allow_single_file = True,
            cfg = "exec",
        ),
        "_arm_gcc_files": attr.label(default = "@arm_gcc//:all", cfg = "exec"),
    },
)
