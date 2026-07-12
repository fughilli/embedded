"""`firmware_binary`: build a board-agnostic `cc_binary` for a specific board
(via an outgoing platform transition) and package it into that board's flashable
artifact — a `.uf2` for RP2350 (picotool) or an app `.bin` for ESP32-C6
(esptool).

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

# Board -> platform, resolved in THIS module's repo (so the transition targets
# @firmware//platforms:* even when the rule is used from another module).
_BOARD_PLATFORM = {
    "rp2350": Label("//platforms:rp2350"),
    "esp32c6": Label("//platforms:esp32c6"),
}

def _board_transition_impl(_settings, attr):
    return {"//command_line_option:platforms": [str(_BOARD_PLATFORM[attr.board])]}

_board_transition = transition(
    implementation = _board_transition_impl,
    inputs = [],
    outputs = ["//command_line_option:platforms"],
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
    else:  # esp32c6
        out = ctx.actions.declare_file(ctx.label.name + ".bin")
        tool = ctx.file._esptool
        tool_files = ctx.attr._esptool_files[DefaultInfo].files
        args.add("--chip", "esp32c6")
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
            values = ["rp2350", "esp32c6"],
            doc = "Which board to build for (drives the transition + packager).",
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
    },
)
