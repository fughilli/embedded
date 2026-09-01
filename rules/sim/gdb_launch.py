"""Shared helper for the `.debug` targets: bring up a GDB remote-stub server,
wait for it to listen, run GDB attached to it, and shut the server down cleanly.

Used by both the emulator debug launcher (server = udbserver on a Unicorn engine,
run in a background thread) and the hardware debug launcher (server = `pyocd
gdbserver`, run as a subprocess).
"""

import socket
import subprocess
import time


def wait_listening(port, timeout=20.0):
    """Block until something is accepting connections on 127.0.0.1:port."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_gdb(gdb, elf, port, load=True, break_at=None, run=False):
    """Launch an interactive GDB attached to the stub on `port`.

    elf       -> loaded for symbols (`file`).
    load      -> also download the image to the target (skip to attach to a
                 running target).
    break_at  -> a symbol/location to break at before handing over (e.g. the app
                 or test entry point).
    run       -> `continue` after setting the breakpoint.
    Returns GDB's exit code.
    """
    args = [gdb, "-q", "-ex", "set pagination off", "-ex", "set confirm off",
            "-ex", "target remote 127.0.0.1:%d" % port]
    if elf:
        args += ["-ex", "file %s" % elf]
    if load:
        args += ["-ex", "load"]
    if break_at:
        args += ["-ex", "tbreak %s" % break_at]
        if run:
            args += ["-ex", "continue"]
    return subprocess.call(args)
