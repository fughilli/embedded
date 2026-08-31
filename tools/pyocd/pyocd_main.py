"""Entry point for the vendored pyOCD flash driver.

Wires the Nix-materialized libusb into pyusb (see ``nix_backend``), then hands
off to pyOCD's real CLI. Run directly (``bazel run //tools/pyocd -- <args>``) or
via the ``pyocd_flash`` rule in //rules:flash.bzl.
"""

import sys

import nix_backend


def main():
    nix_backend.install()
    from pyocd.__main__ import main as pyocd_main

    return pyocd_main()


if __name__ == "__main__":
    sys.exit(main())
