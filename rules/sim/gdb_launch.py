"""Shared helper for the `.debug` targets: bring up a GDB remote-stub server,
wait for it to listen, run GDB attached to it, and shut the server down cleanly.

Used by both the emulator debug launcher (server = udbserver on a Unicorn engine,
run in a background thread) and the hardware debug launcher (server = `pyocd
gdbserver`, run as a subprocess).
"""

import os
import socket
import subprocess
import time


def source_dirs():
    """Directories to add to GDB's source search path so DWARF file paths resolve.

    Bazel records source paths relative to the exec root (`apps/...`, `libs/...`,
    `external/<repo>/...`) but the compilation dir is an ephemeral sandbox that no
    longer exists. Under `bazel run`, BUILD_WORKSPACE_DIRECTORY is the repo root and
    `bazel-<name>` symlinks the exec root (a forest of both first-party packages and
    external repos), so it resolves every recorded path."""
    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if not ws:
        return []
    execroot = os.path.join(ws, "bazel-" + os.path.basename(ws))
    return [d for d in (execroot, ws) if os.path.isdir(d)]


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
    args = [gdb, "-q", "-ex", "set pagination off", "-ex", "set confirm off"]
    for d in source_dirs():  # so DWARF file paths (apps/..., external/...) resolve
        args += ["-ex", "directory %s" % d]
    args += ["-ex", "target remote 127.0.0.1:%d" % port]
    if elf:
        args += ["-ex", "file %s" % elf]
    if load:
        args += ["-ex", "load"]
    if break_at:
        args += ["-ex", "tbreak %s" % break_at]
        if run:
            args += ["-ex", "continue"]
    return subprocess.call(args)
