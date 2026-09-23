"""pyocd_binary: the vendored pyOCD CLI, bundled with a chosen set of CMSIS packs.

The binary is pip pyOCD with the Nix libusb and the `elaphurelink` network probe type.
Every .pack in the given hubs is auto-passed as `--pack` to pack-aware subcommands
(see cmsis_pack_inject.py). Other modules use it to ship their own targets:

    load("@firmware//tools/pyocd:defs.bzl", "pyocd_binary")
    pyocd_binary(name = "pyocd", packs = ["@my_packs//:all_packs"])
"""

load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_python//python:defs.bzl", "py_binary")

def py_entry_binary(name, module, deps, **kwargs):
    """py_binary whose main is a generated `<name>_entry.py` calling `<module>.main()`.

    The entry file lives in the caller's package: newer rules_python precompiles
    sources and rejects a main that belongs to another package (e.g. @firmware's).
    """
    entry = name + "_entry.py"
    write_file(
        name = name + "_entry",
        out = entry,
        content = ["import sys", "import " + module, "sys.exit(" + module + ".main())", ""],
    )
    py_binary(
        name = name,
        srcs = [entry],
        main = entry,
        deps = deps,
        **kwargs
    )

def pyocd_binary(name, packs = [], **kwargs):
    """pyOCD CLI carrying `packs` (hub `all_packs` filegroups from cmsis_packs)."""
    py_entry_binary(
        name = name,
        module = "pyocd_main",
        data = packs,
        deps = [Label("//tools/pyocd:pyocd_runtime")],
        **kwargs
    )
