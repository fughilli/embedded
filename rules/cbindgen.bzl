"""`rust_cbindgen`: generate a C/C++ header from Rust source (Rust -> C/C++).

Wraps the Nix-provided `cbindgen` binary. Runs over one or more Rust source
files (single-file parse mode — no Cargo/dep expansion), emitting a header that
declares the crate's `#[no_mangle] pub extern "C"` items. Use it so C/C++ callers
include a generated, always-in-sync header instead of hand-written `extern "C"`
declarations.

    rust_cbindgen(name = "foo_h", src = "src/lib.rs", out = "foo.h", lang = "c")
    cc_library(name = "foo_hdr", hdrs = [":foo_h"])   # include "<pkg>/foo.h"
"""

def _rust_cbindgen_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out)
    args = ctx.actions.args()
    args.add("--lang", ctx.attr.lang)
    inputs = list(ctx.files.srcs)
    if ctx.file.config:
        args.add("--config", ctx.file.config)
        inputs.append(ctx.file.config)
    args.add("-o", out)
    # cbindgen takes the crate root / a source file as the positional INPUT.
    args.add(ctx.files.srcs[0])

    ctx.actions.run(
        executable = ctx.file._cbindgen,
        arguments = [args],
        inputs = inputs + [ctx.file._cbindgen],
        outputs = [out],
        mnemonic = "Cbindgen",
        progress_message = "cbindgen %{label}",
    )
    return [DefaultInfo(files = depset([out]))]

rust_cbindgen = rule(
    implementation = _rust_cbindgen_impl,
    doc = "Generate a C/C++ header from Rust source via cbindgen.",
    attrs = {
        "srcs": attr.label_list(
            allow_files = [".rs"],
            mandatory = True,
            doc = "Rust source; the first entry is cbindgen's INPUT.",
        ),
        "out": attr.string(mandatory = True, doc = "Generated header filename."),
        "lang": attr.string(default = "c", values = ["c", "c++", "cython"]),
        "config": attr.label(allow_single_file = [".toml"], doc = "Optional cbindgen.toml."),
        "_cbindgen": attr.label(
            default = "@cbindgen//:bin",
            allow_single_file = True,
            cfg = "exec",
        ),
    },
)
