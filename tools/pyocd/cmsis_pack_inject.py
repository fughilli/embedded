"""Auto-pass the vendored CMSIS packs to pyOCD.

The `cmsis_packs` module extension stages every locked `.pack` into the pyocd
binary's runfiles (under a hub repo's ``packs/`` dir). Here we find them and add a
``--pack <file>`` for each, so a pack-provided ``--target`` (e.g. stm32g0b1rctx)
is recognized without the user managing a pack cache. Only the pyOCD subcommands
that accept ``--pack`` are touched, and an explicit ``--pack`` disables injection.
"""

import glob
import os

# pyOCD subcommands that take --pack (the connect/probe group). `pack`, `--help`
# and `--version` do not, so we must not inject for those.
_PACK_SUBCOMMANDS = frozenset({
    "flash", "erase", "load", "gdbserver", "list", "commander", "cmd", "reset",
    "rtt",
})


def staged_packs():
    """Absolute paths of every .pack staged into this binary's runfiles."""
    here = os.path.dirname(os.path.abspath(__file__))
    # Anchor on `.runfiles/` — the execroot path itself contains `_main`, so
    # splitting on `_main` would pick the wrong (too-shallow) root.
    anchor = ".runfiles" + os.sep
    idx = here.find(anchor)
    if idx >= 0:
        root = here[:idx + len(".runfiles")]
    else:
        marker = os.sep + "_main" + os.sep
        root = here.rsplit(marker, 1)[0] if marker in here else here
    # Hub repo lays packs out as <runfiles>/<hub_repo>/packs/<name>.pack.
    return sorted(glob.glob(os.path.join(root, "*", "packs", "*.pack")))


def inject_pack_args(args):
    """Return argv (list, sans argv[0]) with --pack for each staged pack."""
    packs = staged_packs()
    if not packs:
        return args
    sub = next((i for i, a in enumerate(args) if not a.startswith("-")), None)
    if sub is None or args[sub] not in _PACK_SUBCOMMANDS or "--pack" in args:
        return args
    extra = []
    for pack in packs:
        extra += ["--pack", pack]
    return args[:sub + 1] + extra + args[sub + 1:]
