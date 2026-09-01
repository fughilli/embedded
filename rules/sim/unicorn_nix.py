"""Make the `unicorn` Python bindings load the Nix-materialized libunicorn.

The pip `unicorn` wheel bundles a prebuilt libunicorn under ``unicorn/lib``. We do
NOT use it: the native component is supplied by Nix (@unicorn) so it is built from
the repo's pinned nixpkgs, not an opaque manylinux blob. The unicorn loader
(``unicorn/unicorn_py3/unicorn.py``) probes ``$LIBUNICORN_PATH/libunicorn.so.2``
*first*, before its bundled copy, so pointing that env var at the staged Nix lib
is a clean, supported override.

Import this module and call :func:`install` BEFORE importing ``unicorn``.
"""

import os

# libunicorn.so.2 is staged beside this file by //rules/sim:stage_nix_unicorn;
# resolved by __file__-relative path so we need no runfiles library or unstable
# canonical repo name (same approach as //tools/pyocd:nix_backend).
_NIXLIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_nixlib")


def libunicorn_dir():
    """Directory holding the staged Nix libunicorn, or None if not present."""
    return _NIXLIB_DIR if os.path.exists(os.path.join(_NIXLIB_DIR, "libunicorn.so.2")) else None


def install():
    """Point LIBUNICORN_PATH at the staged Nix libunicorn. Idempotent; must run
    before ``import unicorn`` (the loader reads the env var at import time)."""
    d = libunicorn_dir()
    if d:
        os.environ["LIBUNICORN_PATH"] = d
    return d
