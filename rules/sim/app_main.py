"""Entry point for ``simulation_app`` targets — full-app emulation.

Boots the exact firmware ELF from reset under Unicorn with the test's virtual
:mod:`peripherals`, then hands the result to a ``checker`` module's ``check(result)``
for assertions. Fails non-zero if the app faults, a check fails, or (when the
checker cares) the app never exhibited the expected behavior within the budget.
"""

import argparse
import importlib
import json
import sys

from python.runfiles import runfiles

import harness
import peripherals as periph


def _resolve(rf, rloc):
    path = rf.Rlocation(rloc)
    if not path:
        sys.exit("runfiles: could not resolve %r" % rloc)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--emu", required=True)
    ap.add_argument("--plugins", required=True,
                    help="comma-separated plugin module names composing the device model")
    ap.add_argument("--checker", default="", help="import name of the checker module")
    ap.add_argument("--max_cycles", type=int, default=None)
    args = ap.parse_args()

    rf = runfiles.Create()
    elf_path = _resolve(rf, args.elf)
    with open(_resolve(rf, args.emu)) as f:
        emu = json.load(f)

    # Compose the device model from the plugin list: import each (running its
    # @sim_peripheral registrations), then instantiate everything registered.
    periph.import_plugins(args.plugins.split(","))
    models = periph.instantiate()
    if not models:
        sys.exit("plugins %r registered no peripherals" % args.plugins)

    print("== boot ==")
    print("  arch=%s  boot=%s  vt=0x%08x" %
          (emu["architecture"], emu.get("boot"), emu.get("vector_table", 0)))
    print("  device model: %s" %
          ", ".join("%s(%s)" % (type(m).sim_name, type(m).__name__) for m in models))
    peripherals = models
    result = harness.boot_app(elf_path, emu, peripherals, max_cycles=args.max_cycles)
    print("  stopped: %s (instructions counted: %d)" %
          ("cycle budget" if result.hit_budget else "peripheral done()",
           result.instructions))

    failures = []
    if args.checker:
        cmod = importlib.import_module(args.checker)
        if not hasattr(cmod, "check"):
            sys.exit("checker module %r has no check(result)" % args.checker)
        print("== check ==")
        try:
            cmod.check(result)
        except AssertionError as e:
            failures.append("check failed: %s" % e)

    if failures:
        print("\nFAILED (%d):" % len(failures))
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("\nPASS")


if __name__ == "__main__":
    main()
