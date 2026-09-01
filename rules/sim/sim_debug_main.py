"""Emulator `.debug` launcher — interactive GDB against the firmware under Unicorn.

Generated as `<name>.debug` by simulation_app / simulation_test. It sets the
emulator up exactly as the run would (same ELF, memory map, peripherals / stimulus
frame) but, instead of free-running, starts a udbserver GDB stub on the Unicorn
engine in a background thread and launches GDB attached to it, halted at the entry
point so you can set breakpoints, inspect memory, and single-step. When GDB exits,
the process exits and the daemon server thread goes with it.

  * app mode:  boots the firmware from reset, breaks at the application entry
               (main, or the reset handler).
  * test mode: sets up the first stimulus's call frame, breaks at its entrypoint.
"""

import argparse
import json
import sys
import threading

import unicorn_nix

unicorn_nix.install()  # load the Nix libunicorn before unicorn/udbserver bind it

from python.runfiles import runfiles  # noqa: E402

import gdb_launch  # noqa: E402
import harness  # noqa: E402
import peripherals as periph  # noqa: E402
import uc_gdbserver  # noqa: E402  (drop-in for udbserver; handles Cortex-M)


def _resolve(rf, rloc):
    p = rf.Rlocation(rloc)
    if not p:
        sys.exit("runfiles: could not resolve %r" % rloc)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["app", "test"])
    ap.add_argument("--elf", required=True)
    ap.add_argument("--emu", required=True)
    ap.add_argument("--gdb", required=True)
    ap.add_argument("--port", type=int, default=0)  # 0 = ephemeral (avoid clashes)
    ap.add_argument("--plugins", default="")
    ap.add_argument("--generator", default="")
    ap.add_argument("--break_at", default="")
    args = ap.parse_args()

    rf = runfiles.Create()
    elf = _resolve(rf, args.elf)
    gdb = _resolve(rf, args.gdb)
    with open(_resolve(rf, args.emu)) as f:
        emu = json.load(f)

    if args.mode == "app":
        periph.import_plugins(args.plugins.split(",") if args.plugins else [])
        uc, start_pc, symbols = harness.build_app(elf, emu, periph.instantiate())
        break_at = args.break_at or ("main" if "main" in symbols else None)
    else:  # test
        import importlib
        import inspect
        from stimulus import SimulationStimulusGenerator
        gmod = importlib.import_module(args.generator)
        gen = next(o() for _, o in inspect.getmembers(gmod, inspect.isclass)
                   if issubclass(o, SimulationStimulusGenerator)
                   and o is not SimulationStimulusGenerator and not inspect.isabstract(o))
        stimuli = list(gen.stimuli())
        if not stimuli:
            sys.exit("no stimuli to debug")
        sim = harness.Simulator(elf, emu)
        entry = sim.prepare(stimuli[0], 0)
        uc, start_pc = sim.uc, entry
        break_at = args.break_at or stimuli[0].entrypoint
        print("debugging first stimulus: %s" % stimuli[0].label(0))

    # Serve the GDB stub on the engine in a daemon thread; GDB drives execution.
    stub = uc_gdbserver.GdbStub(uc, start_pc)
    ready = threading.Event()
    t = threading.Thread(target=lambda: stub.serve(args.port, ready=ready), daemon=True)
    t.start()
    if not ready.wait(timeout=20):
        sys.exit("gdbserver did not start listening")
    print("== gdbserver on :%d — launching GDB (break at %s) ==" % (stub.port, break_at))
    # No `load` under the emulator: the image is already in emulated memory.
    rc = gdb_launch.run_gdb(gdb, elf, stub.port, load=False, break_at=break_at, run=False)
    sys.exit(rc)


if __name__ == "__main__":
    main()
