"""Assert that pyOCD's USB layer binds to the Nix-materialized libusb.

`bazel run //tools/pyocd:verify_backend` — no hardware needed. Confirms the
wrapper (nix_backend) makes pyusb resolve a real libusb1 backend from the staged
Nix shared object, which is the whole point of substituting the binary dep.
"""

import ctypes.util
import os
import sys

import nix_backend


def main():
    nix_backend.install()

    staged = nix_backend.libusb_path()
    print("staged Nix libusb:", staged)
    if not (staged and os.path.exists(staged)):
        print("FAIL: staged libusb missing", file=sys.stderr)
        return 1
    if "/execroot/" not in staged and ".runfiles/" not in staged and "/sandbox/" not in staged:
        # Sanity: it should be the Bazel-staged copy, not a system lib.
        print("WARN: libusb path is not under a Bazel tree:", staged, file=sys.stderr)

    resolved = ctypes.util.find_library("usb-1.0")
    print("find_library('usb-1.0') ->", resolved)

    import usb.backend.libusb1 as libusb1

    backend = libusb1.get_backend()
    print("pyusb libusb1 backend:", backend)
    if backend is None:
        print("FAIL: pyusb found no libusb backend", file=sys.stderr)
        return 1
    if resolved != staged:
        print("FAIL: pyusb did not resolve the Nix libusb", file=sys.stderr)
        return 1

    print("OK: pyOCD/pyusb will dlopen the Nix libusb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
