"""pyocd_binary: the vendored pyOCD CLI, bundled with a chosen set of CMSIS packs.

The binary is pip pyOCD with the Nix libusb and the `elaphurelink` network probe type.
Every .pack in the given hubs is auto-passed as `--pack` to pack-aware subcommands
(see cmsis_pack_inject.py). Other modules use it to ship their own targets:

    load("@firmware//tools/pyocd:defs.bzl", "pyocd_binary")
    pyocd_binary(name = "pyocd", packs = ["@my_packs//:all_packs"])
"""

load("@rules_python//python:defs.bzl", "py_binary")

def pyocd_binary(name, packs = [], **kwargs):
    """pyOCD CLI carrying `packs` (hub `all_packs` filegroups from cmsis_packs)."""
    py_binary(
        name = name,
        srcs = [Label("//tools/pyocd:pyocd_main.py")],
        main = Label("//tools/pyocd:pyocd_main.py"),
        data = packs,
        deps = [Label("//tools/pyocd:pyocd_runtime")],
        **kwargs
    )
