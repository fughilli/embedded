"""`embedded_binary`: retarget a firmware cc_binary to a specific board.

It wraps a normal `cc_binary` (which builds the `.elf`) and applies an outgoing
transition that sets `//command_line_option:platforms` to the given board. That
retargets the *entire* subgraph — the cc_toolchain resolves to the board's
cross-GCC and any `select()` on `//platforms:board` in the deps resolves to the
right platform-support code — from one `bazel build //apps/...:...` with no
`--platforms` flag on the command line.
"""

def _platform_transition_impl(_settings, attr):
    return {"//command_line_option:platforms": [attr.platform]}

_platform_transition = transition(
    implementation = _platform_transition_impl,
    inputs = [],
    outputs = ["//command_line_option:platforms"],
)

def _embedded_binary_impl(ctx):
    # `binary` is transitioned, so ctx.attr.binary is a 1-element list.
    dep = ctx.attr.binary[0]
    elf = dep[DefaultInfo].files_to_run.executable

    # Republish under a stable, discoverable name.
    out = ctx.actions.declare_file(ctx.label.name + ".elf")
    ctx.actions.symlink(output = out, target_file = elf)

    return [DefaultInfo(
        files = depset([out]),
        runfiles = ctx.runfiles(files = [out]),
    )]

embedded_binary = rule(
    implementation = _embedded_binary_impl,
    doc = "Builds `binary` (a cc_binary) for `platform`, exposing its .elf.",
    attrs = {
        "binary": attr.label(
            mandatory = True,
            cfg = _platform_transition,
            doc = "The cc_binary that produces the firmware .elf.",
        ),
        "platform": attr.label(
            mandatory = True,
            doc = "The //platforms:* target to build `binary` for.",
        ),
    },
)
