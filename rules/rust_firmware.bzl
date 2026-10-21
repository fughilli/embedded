"""Rust static libraries for linking into ESP-IDF / Arduino firmware.

`firmware_rust_library(lib = ":my_rust_static_library")` re-exports a
rust_static_library with Rust's `compiler_builtins` objects removed, using
the target board's own `ar` (from its cc toolchain).

Why: rustc bundles compiler_builtins into every staticlib, and its
intrinsics (memset/memcpy with the `mem` feature, __udivdi3, soft-float
ops, ...) are *defined* there — weakly, but ESP-IDF supplies its versions of
the same symbols from ROM through linker-script PROVIDE(), which only applies
when no definition exists at all. So the Rust copies win, land in flash, and
ESP-IDF code that runs with the flash cache disabled (flash init, NVS writes,
ISRs) jumps into flash: "Cache error" panic at boot (seen: memset during
esp_flash_init). Without the bundled builtins, Rust's references resolve to
the ROM / libgcc / newlib definitions the platform places correctly; anything
Rust needs that the C side lacks fails at link time instead of at runtime.
"""

load("@bazel_tools//tools/build_defs/cc:action_names.bzl", "ACTION_NAMES")
load("@bazel_tools//tools/cpp:toolchain_utils.bzl", "find_cpp_toolchain", "use_cpp_toolchain")

def _firmware_rust_library_impl(ctx):
    archives = [f for f in ctx.attr.lib[DefaultInfo].files.to_list() if f.extension == "a"]
    if len(archives) != 1:
        fail("expected exactly one .a from %s, got %s" % (ctx.attr.lib.label, archives))
    src = archives[0]
    cc_toolchain = find_cpp_toolchain(ctx)
    feature_configuration = cc_common.configure_features(
        ctx = ctx,
        cc_toolchain = cc_toolchain,
        requested_features = ctx.features,
        unsupported_features = ctx.disabled_features,
    )
    # The board toolchains declare tools via action configs, so ask for the
    # static-library archiver rather than the legacy ar_executable.
    ar = cc_common.get_tool_for_action(
        feature_configuration = feature_configuration,
        action_name = ACTION_NAMES.cpp_link_static_library,
    )
    out = ctx.actions.declare_file("lib%s.a" % ctx.label.name)
    ctx.actions.run_shell(
        inputs = [src],
        tools = cc_toolchain.all_files,
        outputs = [out],
        arguments = [src.path, out.path, ar],
        command = """
set -eu
cp "$1" "$2"
chmod u+w "$2"
listing=$("$3" t "$2")
members=$(printf '%s\n' "$listing" | grep compiler_builtins || true)
if [ -n "$members" ]; then "$3" d "$2" $members; fi
if "$3" t "$2" | grep -q compiler_builtins; then
  echo "compiler_builtins members survived in $2" >&2
  exit 1
fi
""",
        mnemonic = "StripRustBuiltins",
        progress_message = "Removing compiler_builtins from %s" % src.short_path,
    )
    library = cc_common.create_library_to_link(
        actions = ctx.actions,
        feature_configuration = feature_configuration,
        cc_toolchain = cc_toolchain,
        static_library = out,
        alwayslink = False,
    )
    linker_input = cc_common.create_linker_input(
        owner = ctx.label,
        libraries = depset([library]),
    )
    return [
        DefaultInfo(files = depset([out])),
        CcInfo(linking_context = cc_common.create_linking_context(
            linker_inputs = depset([linker_input]),
        )),
    ]

firmware_rust_library = rule(
    implementation = _firmware_rust_library_impl,
    doc = "A rust_static_library minus its bundled compiler_builtins (see module doc).",
    attrs = {
        "lib": attr.label(mandatory = True, doc = "A rust_static_library target."),
    },
    fragments = ["cpp"],
    toolchains = use_cpp_toolchain(),
)
