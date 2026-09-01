"""`pyocd_debug` launcher — interactive GDB against a real target over a probe.

Starts `pyocd gdbserver` (the hermetic //tools/pyocd driver: pip pyOCD + Nix
libusb) as a background subprocess, waits for it to listen, then runs GDB attached
to it — optionally loading the firmware first (skip --load to attach to and debug
an already-running target). When GDB exits, the gdbserver is shut down.
"""

import argparse
import subprocess
import sys

from python.runfiles import runfiles

import gdb_launch


def _resolve(rf, rloc):
    p = rf.Rlocation(rloc)
    if not p:
        sys.exit("runfiles: could not resolve %r" % rloc)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--gdb", required=True)
    ap.add_argument("--pyocd", required=True)
    ap.add_argument("--port", type=int, default=3333)
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--frequency", default="")
    args, passthrough = ap.parse_known_args()

    rf = runfiles.Create()
    elf = _resolve(rf, args.elf)
    gdb = _resolve(rf, args.gdb)
    pyocd = _resolve(rf, args.pyocd)

    cmd = [pyocd, "gdbserver", "--target", args.target, "--port", str(args.port)]
    if args.frequency:
        cmd += ["--frequency", args.frequency]
    cmd += passthrough  # e.g. --probe <uid>

    # The nested //tools/pyocd py_binary is a data dep, so its modules live in THIS
    # launcher's runfiles tree — keep RUNFILES_DIR/MANIFEST so it resolves them.
    print("== starting pyocd gdbserver (target %s, port %d) ==" % (args.target, args.port))
    server = subprocess.Popen(cmd)
    try:
        if not gdb_launch.wait_listening(args.port, timeout=30):
            sys.exit("pyocd gdbserver did not start listening (probe connected?)")
        rc = gdb_launch.run_gdb(gdb, elf, args.port, load=args.load, break_at=None)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    sys.exit(rc)


if __name__ == "__main__":
    main()
