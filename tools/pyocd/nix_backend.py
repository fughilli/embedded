"""Make pyusb / pyOCD load the Nix-materialized libusb.

pyusb locates libusb through ``ctypes.util.find_library('usb-1.0')``, which on
Linux consults ldconfig / gcc and *ignores* ``LD_LIBRARY_PATH`` and preloaded
objects (macOS is similar via dyld). Inside a hermetic Bazel runfiles tree there
is no system libusb, so the lookup fails and pyusb reports "No backend
available". We stage the Nix libusb next to this module (see the
``stage_nix_libs`` genrule; a ``.so`` on Linux or ``.dylib`` on macOS, under a
fixed name) and point ``find_library`` straight at it, so the Nix build is the
library pyOCD actually dlopens — not the prebuilt blob inside the libusb-package
wheel.
"""

import ctypes
import ctypes.util
import os

# Shared objects staged (under fixed sonames) beside this file by the
# //tools/pyocd:stage_nix_libs genrule; resolved by __file__-relative path so we
# need no runfiles library or unstable canonical repo name.
_NIXLIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_nixlib")

# find_library(name) -> staged file, covering the names pyusb probes for libusb.
_LIB_FOR_NAME = {
    "usb-1.0": "libusb-1.0.so.0",
    "libusb-1.0": "libusb-1.0.so.0",
    "usb": "libusb-1.0.so.0",
}


def _staged(soname):
    path = os.path.join(_NIXLIB_DIR, soname)
    return path if os.path.exists(path) else None


def libusb_path():
    """Absolute path of the staged Nix libusb, or None if unavailable."""
    return _staged("libusb-1.0.so.0")


def install():
    """Patch ``find_library`` (globally + in pyusb) to return the Nix libs, and
    preload libusb so its soname is already resolved in-process. Idempotent."""
    libusb = libusb_path()
    if libusb:
        try:
            ctypes.CDLL(libusb, mode=ctypes.RTLD_GLOBAL)
        except OSError:
            pass

    original = ctypes.util.find_library

    def find_library(name):
        soname = _LIB_FOR_NAME.get(name)
        staged = _staged(soname) if soname else None
        return staged or original(name)

    ctypes.util.find_library = find_library
    # pyusb binds find_library at import time into its own module namespace.
    try:
        import usb.libloader

        usb.libloader.find_library = find_library
    except ImportError:
        pass
    return find_library
