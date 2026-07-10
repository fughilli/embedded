"""Reusable GCC cross-compiler cc_toolchain_config for bare-metal boards.

The compiler binaries come from a Nix-provided external repo (e.g. @arm_gcc).
We reference each tool as a Bazel File (label attr) and build `action_config`s
with `tool(tool = <File>)` — this resolves correctly across repos, unlike string
`tool_paths`, whose interpretation depends on the (bzlmod-canonical, unstable)
external repo directory name.

The board-specific -mcpu/-march/-mfloat-abi/... flags are passed in via
`compile_flags` / `link_flags`, so one rule serves both RP2350 and ESP32-C6.
"""

load("@rules_cc//cc:action_names.bzl", "ACTION_NAMES")
load(
    "@rules_cc//cc:cc_toolchain_config_lib.bzl",
    "action_config",
    "feature",
    "flag_group",
    "flag_set",
    "tool",
)

_COMPILE_ACTIONS = [
    ACTION_NAMES.c_compile,
    ACTION_NAMES.cpp_compile,
    ACTION_NAMES.assemble,
    ACTION_NAMES.preprocess_assemble,
]

_LINK_ACTIONS = [
    ACTION_NAMES.cpp_link_executable,
    ACTION_NAMES.cpp_link_dynamic_library,
    ACTION_NAMES.cpp_link_nodeps_dynamic_library,
]

def _impl(ctx):
    gcc = ctx.file.gcc
    gpp = ctx.file.gpp
    ar = ctx.file.ar
    strip = ctx.file.strip

    # Map each action to the tool that performs it. C++ compile + linking go
    # through g++ (drives the correct default libs); C/assembly through gcc;
    # archiving through ar; stripping through strip.
    action_configs = [
        action_config(
            action_name = ACTION_NAMES.c_compile,
            enabled = True,
            tools = [tool(tool = gcc)],
        ),
        action_config(
            action_name = ACTION_NAMES.assemble,
            enabled = True,
            tools = [tool(tool = gcc)],
        ),
        action_config(
            action_name = ACTION_NAMES.preprocess_assemble,
            enabled = True,
            tools = [tool(tool = gcc)],
        ),
        action_config(
            action_name = ACTION_NAMES.cpp_compile,
            enabled = True,
            tools = [tool(tool = gpp)],
        ),
        action_config(
            action_name = ACTION_NAMES.cpp_link_executable,
            enabled = True,
            tools = [tool(tool = gpp)],
        ),
        action_config(
            action_name = ACTION_NAMES.cpp_link_dynamic_library,
            enabled = True,
            tools = [tool(tool = gpp)],
        ),
        action_config(
            action_name = ACTION_NAMES.cpp_link_nodeps_dynamic_library,
            enabled = True,
            tools = [tool(tool = gpp)],
        ),
        action_config(
            action_name = ACTION_NAMES.cpp_link_static_library,
            enabled = True,
            tools = [tool(tool = ar)],
        ),
        action_config(
            action_name = ACTION_NAMES.strip,
            enabled = True,
            tools = [tool(tool = strip)],
        ),
    ]

    default_compile = feature(
        name = "default_compile_flags",
        enabled = True,
        flag_sets = [flag_set(
            actions = _COMPILE_ACTIONS,
            flag_groups = [flag_group(flags = ctx.attr.compile_flags)],
        )] if ctx.attr.compile_flags else [],
    )

    default_link = feature(
        name = "default_link_flags",
        enabled = True,
        flag_sets = [flag_set(
            actions = _LINK_ACTIONS,
            flag_groups = [flag_group(flags = ctx.attr.link_flags)],
        )] if ctx.attr.link_flags else [],
    )

    return cc_common.create_cc_toolchain_config_info(
        ctx = ctx,
        toolchain_identifier = ctx.attr.toolchain_identifier,
        target_cpu = ctx.attr.target_cpu,
        target_system_name = ctx.attr.target_system_name,
        compiler = "gcc",
        target_libc = "newlib",
        abi_version = "unknown",
        abi_libc_version = "unknown",
        host_system_name = "local",
        action_configs = action_configs,
        features = [default_compile, default_link],
        # Absolute /nix/store include dirs vary by pin; allowing the whole store
        # as a prefix suppresses "undeclared inclusion" errors hermetically.
        # Tighten to the exact reported dirs once known (see WORKLOG).
        cxx_builtin_include_directories = ctx.attr.builtin_include_dirs,
    )

cc_toolchain_config = rule(
    implementation = _impl,
    attrs = {
        "toolchain_identifier": attr.string(mandatory = True),
        "target_cpu": attr.string(mandatory = True),
        "target_system_name": attr.string(mandatory = True),
        "gcc": attr.label(allow_single_file = True, mandatory = True),
        "gpp": attr.label(allow_single_file = True, mandatory = True),
        "ar": attr.label(allow_single_file = True, mandatory = True),
        "strip": attr.label(allow_single_file = True, mandatory = True),
        "compile_flags": attr.string_list(default = []),
        "link_flags": attr.string_list(default = []),
        "builtin_include_dirs": attr.string_list(default = ["/nix/store"]),
    },
    provides = [CcToolchainConfigInfo],
)
