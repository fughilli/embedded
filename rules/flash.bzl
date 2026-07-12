"""Convenience `bazel run` targets that flash firmware to a connected board.

`esptool_flash` writes a full bootable ESP32 image (bootloader + partition table
+ boot_app0 + app) via esptool; `picotool_flash` loads a UF2 via picotool. Both
build the firmware as a normal dependency, then exec the Nix-provided tool over
the artifacts. Extra CLI args pass through, e.g.:

    bazel run //apps/blink_esp32c6:flash -- --port /dev/ttyACM0
"""

# Canonical Bazel Bash runfiles library initializer (v3).
_RUNFILES_INIT = r'''#!/usr/bin/env bash
set -euo pipefail
# --- begin runfiles.bash initialization v3 ---
set -uo pipefail; set +e; f=bazel_tools/tools/bash/runfiles/runfiles.bash
source "${RUNFILES_DIR:-/dev/null}/$f" 2>/dev/null || \
  source "$(grep -sm1 "^$f " "${RUNFILES_MANIFEST_FILE:-/dev/null}" | cut -f2- -d' ')" 2>/dev/null || \
  source "$0.runfiles/$f" 2>/dev/null || \
  { echo>&2 "ERROR: cannot find runfiles.bash"; exit 1; }; f=; set -e
# --- end runfiles.bash initialization v3 ---
'''

def _rloc(ctx, f):
    # Runfiles lookup key for a File: strip the leading `../` for external repos,
    # otherwise prefix with the (main) workspace name.
    sp = f.short_path
    if sp.startswith("../"):
        return sp[len("../"):]
    return ctx.workspace_name + "/" + sp

def _launcher(ctx, tool_file, parts, runfiles_extra):
    """parts: ordered list of ('lit', str) or ('file', File) forming the argv
    after the tool. runfiles_extra: extra depset/list of files to stage."""
    argv = ['"$(rlocation %s)"' % _rloc(ctx, tool_file), '"$@"']
    files = [tool_file]
    for kind, val in parts:
        if kind == "lit":
            argv.append("'%s'" % val)
        else:
            argv.append('"$(rlocation %s)"' % _rloc(ctx, val))
            files.append(val)
    out = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.write(out, _RUNFILES_INIT + "exec " + " ".join(argv) + "\n", is_executable = True)
    runfiles = ctx.runfiles(files = files + runfiles_extra)
    runfiles = runfiles.merge(ctx.attr._bash_runfiles[DefaultInfo].default_runfiles)
    return [DefaultInfo(executable = out, runfiles = runfiles)]

# ---------------------------------------------------------------------------
# ESP32 (esptool)
# ---------------------------------------------------------------------------
def _esptool_flash_impl(ctx):
    parts = [
        ("lit", "--chip"), ("lit", ctx.attr.chip),
        ("lit", "write-flash"),
        ("lit", "--flash-mode"), ("lit", ctx.attr.flash_mode),
        ("lit", "--flash-freq"), ("lit", ctx.attr.flash_freq),
        ("lit", "--flash-size"), ("lit", ctx.attr.flash_size),
        ("lit", ctx.attr.bootloader_offset), ("file", ctx.file.bootloader),
        ("lit", "0x8000"), ("file", ctx.file.partitions),
        ("lit", "0xe000"), ("file", ctx.file.boot_app0),
        ("lit", "0x10000"), ("file", ctx.file.app),
    ]
    return _launcher(ctx, ctx.file.tool, parts, ctx.files.tool_data)

esptool_flash = rule(
    implementation = _esptool_flash_impl,
    executable = True,
    doc = "Flash a full bootable ESP32 image (bootloader+partitions+app).",
    attrs = {
        "chip": attr.string(default = "esp32c6"),
        "app": attr.label(mandatory = True, allow_single_file = True),
        # These default to this module's (esp32c6) artifacts — the label defaults
        # resolve in THIS .bzl's repo, so consumers only pass `app`. Override for
        # another chip / partition layout.
        "bootloader": attr.label(
            default = "//libs/board:esp32c6_bootloader_bin",
            allow_single_file = True,
        ),
        "partitions": attr.label(
            default = "@arduino_esp32//:partitions_default",
            allow_single_file = True,
        ),
        "boot_app0": attr.label(
            default = "@arduino_esp32//:boot_app0",
            allow_single_file = True,
        ),
        # 0x0 on ESP32-C2/C3/C6/H2/S3; the original ESP32 and S2 use 0x1000.
        "bootloader_offset": attr.string(default = "0x0"),
        # "keep" = don't re-stamp the bootloader image header at write time;
        # the header already carries the right mode/freq/size from elf2image.
        "flash_mode": attr.string(default = "keep"),
        "flash_freq": attr.string(default = "keep"),
        "flash_size": attr.string(default = "keep"),
        "tool": attr.label(default = "@esptool//:bin", allow_single_file = True, cfg = "exec"),
        "tool_data": attr.label(default = "@esptool//:all", allow_files = True, cfg = "exec"),
        "_bash_runfiles": attr.label(default = "@bazel_tools//tools/bash/runfiles"),
    },
)

# ---------------------------------------------------------------------------
# RP2350 (picotool)
# ---------------------------------------------------------------------------
def _picotool_flash_impl(ctx):
    # `load -x` writes the UF2 and reboots into the app. Requires the board in
    # BOOTSEL mode (USB mass-storage / picoboot).
    parts = [("lit", "load"), ("lit", "-x"), ("file", ctx.file.uf2)]
    return _launcher(ctx, ctx.file.tool, parts, ctx.files.tool_data)

picotool_flash = rule(
    implementation = _picotool_flash_impl,
    executable = True,
    doc = "Load a UF2 to an RP2350 in BOOTSEL mode via picotool.",
    attrs = {
        "uf2": attr.label(mandatory = True, allow_single_file = True),
        "tool": attr.label(default = "@picotool//:bin", allow_single_file = True, cfg = "exec"),
        "tool_data": attr.label(default = "@picotool//:all", allow_files = True, cfg = "exec"),
        "_bash_runfiles": attr.label(default = "@bazel_tools//tools/bash/runfiles"),
    },
)
