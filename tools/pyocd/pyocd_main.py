"""Entry point for the vendored pyOCD flash driver.

Wires the Nix-materialized libusb into pyusb (see ``nix_backend``), then hands
off to pyOCD's real CLI. Run directly (``bazel run //tools/pyocd -- <args>``) or
via the ``pyocd_flash`` rule in //rules:flash.bzl.
"""

import sys

import cmsis_pack_inject
import elaphurelink_probe
import nix_backend


def main():
    nix_backend.install()
    # Make vendored CMSIS packs (e.g. the STM32G0 DFP) available to pack-aware
    # subcommands, so pack-provided --targets are recognized out of the box.
    sys.argv[1:] = cmsis_pack_inject.inject_pack_args(sys.argv[1:])
    # Network CMSIS-DAP probes (wireless ESP32 DAP): `--uid elaphurelink:<host>`.
    elaphurelink_probe.register()
    from pyocd.__main__ import main as pyocd_main

    return pyocd_main()


if __name__ == "__main__":
    sys.exit(main())
