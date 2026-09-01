"""A minimal GDB remote-serial-protocol stub for a Unicorn engine.

Why not udbserver (bet4it/udbserver), as first intended: udbserver 0.3.0 panics on
a Cortex-M engine — it does `Mode::try_from(uc.query(MODE))` and Unicorn returns
THUMB|MCLASS (0x30), which isn't a single Mode variant, so it unwraps an Err. Our
firmware needs MCLASS (RP2350/STM32G0 use M-profile-only instructions), so we can't
drop it. This ~200-line stub drives the real MCLASS engine directly instead.

Supported: qSupported / target.xml (org.gnu.gdb.arm.m-profile register layout),
read/write registers (g/G/p/P), read/write memory (m/M), software+hardware
breakpoints (Z0/Z1/z0/z1), continue (c / vCont;c) with Ctrl-C interrupt, single
step (s / vCont;s), halt reason (?), detach/kill (D/k). Enough for setting
breakpoints, inspecting memory, and stepping through code.
"""

import os
import socket
import sys

from unicorn import UC_HOOK_BLOCK, UC_HOOK_CODE, UcError
import unicorn.arm_const as _arm

_DEBUG = bool(os.environ.get("GDBSTUB_DEBUG"))


def _log(*a):
    if _DEBUG:
        print("[gdbstub]", *a, file=sys.stderr, flush=True)

# m-profile core registers, in GDB's expected g/G order.
_REGS = ["R%d" % i for i in range(13)] + ["SP", "LR", "PC", "XPSR"]
_UCREG = [getattr(_arm, "UC_ARM_REG_" + n) for n in _REGS]

_TARGET_XML = (
    '<?xml version="1.0"?>\n<!DOCTYPE target SYSTEM "gdb-target.dtd">\n'
    '<target version="1.0"><architecture>arm</architecture>'
    '<feature name="org.gnu.gdb.arm.m-profile">'
    + "".join('<reg name="%s" bitsize="32"/>' % n.lower() for n in _REGS[:13])
    + '<reg name="sp" bitsize="32" type="data_ptr"/>'
      '<reg name="lr" bitsize="32"/>'
      '<reg name="pc" bitsize="32" type="code_ptr"/>'
      '<reg name="xpsr" bitsize="32"/>'
    + "</feature></target>"
)


def _cksum(s):
    return sum(s.encode()) & 0xFF


class GdbStub:
    def __init__(self, uc, start_pc=None):
        self.uc = uc
        self.breakpoints = set()
        self.port = None  # the actual bound port (set by serve; ephemeral if 0)
        if start_pc is not None:
            uc.reg_write(_arm.UC_ARM_REG_PC, start_pc)

    # -- packet I/O ---------------------------------------------------------
    def _send(self, conn, payload):
        conn.sendall(b"$" + payload.encode() + b"#%02x" % _cksum(payload))

    def _recv_packet(self, conn):
        """Read one $...#cc packet (ack it). Returns the payload, or '\x03' for an
        interrupt, or None on EOF. Skips inter-packet '+'/'-' acks."""
        while True:  # skip to the packet start, handling acks + interrupts
            b = conn.recv(1)
            if not b:
                return None
            if b == b"\x03":
                return "\x03"
            if b == b"$":
                break
        buf = b""
        while True:
            b = conn.recv(1)
            if not b:
                return None
            if b == b"#":
                conn.recv(2)  # discard the two checksum hex digits
                break
            buf += b
        conn.sendall(b"+")
        return buf.decode(errors="replace")

    # -- register / memory helpers -----------------------------------------
    def _read_regs(self):
        out = ""
        for r in _UCREG:
            out += int(self.uc.reg_read(r) & 0xFFFFFFFF).to_bytes(4, "little").hex()
        return out

    def _write_regs(self, data):
        for i, r in enumerate(_UCREG):
            chunk = data[i * 8:(i + 1) * 8]
            if len(chunk) == 8:
                self.uc.reg_write(r, int.from_bytes(bytes.fromhex(chunk), "little"))

    # -- execution ----------------------------------------------------------
    def _run(self, conn, single_step):
        """Continue or step; return the stop-reply packet. Ctrl-C from `conn`
        (and any breakpoint) halts a continue."""
        pc = self.uc.reg_read(_arm.UC_ARM_REG_PC) | 1  # thumb bit (M-profile)
        handles = []
        for bp in self.breakpoints:
            handles.append(self.uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: u.emu_stop(),
                                            begin=bp, end=bp))
        if not single_step:
            conn.setblocking(False)

            def watch(u, a, s, d):
                try:
                    if conn.recv(1) == b"\x03":
                        u.emu_stop()
                except (BlockingIOError, OSError):
                    pass
            handles.append(self.uc.hook_add(UC_HOOK_BLOCK, watch))
        try:
            # A large instruction bound for continue (breakpoints stop earlier via
            # hooks; count=0 doesn't run here). If it's hit with no breakpoint, the
            # session just pauses and the user can continue again.
            self.uc.emu_start(pc, 0, timeout=0, count=1 if single_step else 100_000_000)
        except UcError:
            pass
        finally:
            conn.setblocking(True)
            for h in handles:
                self.uc.hook_del(h)
        return "S05"  # SIGTRAP

    # -- packet dispatch ----------------------------------------------------
    def _handle(self, conn, pkt):
        if pkt == "\x03":
            return "S02"
        if pkt.startswith("qSupported"):
            return "PacketSize=4000;qXfer:features:read+;swbreak+;hwbreak+"
        if pkt.startswith("qXfer:features:read:target.xml:"):
            off, length = (int(x, 16) for x in pkt.split(":")[-1].split(","))
            chunk = _TARGET_XML[off:off + length]
            return ("l" if off + length >= len(_TARGET_XML) else "m") + chunk
        if pkt == "?":
            return "S05"
        if pkt in ("qAttached",):
            return "1"
        if pkt == "g":
            return self._read_regs()
        if pkt.startswith("G"):
            self._write_regs(pkt[1:])
            return "OK"
        if pkt.startswith("p"):
            n = int(pkt[1:], 16)
            if n < len(_UCREG):
                return int(self.uc.reg_read(_UCREG[n]) & 0xFFFFFFFF).to_bytes(4, "little").hex()
            return "00000000"
        if pkt.startswith("P"):
            n, val = pkt[1:].split("=")
            n = int(n, 16)
            if n < len(_UCREG):
                self.uc.reg_write(_UCREG[n], int.from_bytes(bytes.fromhex(val), "little"))
            return "OK"
        if pkt.startswith("m"):
            addr, length = (int(x, 16) for x in pkt[1:].split(","))
            try:
                return bytes(self.uc.mem_read(addr, length)).hex()
            except UcError:
                return "E01"
        if pkt.startswith("M"):
            head, data = pkt[1:].split(":")
            addr, _ = (int(x, 16) for x in head.split(","))
            try:
                self.uc.mem_write(addr, bytes.fromhex(data))
                return "OK"
            except UcError:
                return "E01"
        if pkt[:1] in ("Z", "z") and pkt[1:2] in ("0", "1"):
            addr = int(pkt.split(",")[1], 16) & ~1  # drop the thumb bit
            (self.breakpoints.add if pkt[0] == "Z" else self.breakpoints.discard)(addr)
            return "OK"
        if pkt == "c" or pkt.startswith("vCont;c") or pkt.startswith("C"):
            return self._run(conn, single_step=False)
        if pkt == "s" or pkt.startswith("vCont;s") or pkt.startswith("S"):
            return self._run(conn, single_step=True)
        if pkt == "vCont?":
            return "vCont;c;C;s;S"
        if pkt in ("D", "k"):
            return "OK"
        return ""  # unsupported -> empty (GDB treats as "not supported")

    def serve(self, port, ready=None):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))  # port 0 -> OS picks a free ephemeral port
        self.port = srv.getsockname()[1]
        srv.listen(1)
        if ready is not None:
            ready.set()  # signal listening WITHOUT a probe connection (single accept)
        conn, _ = srv.accept()
        try:
            while True:
                pkt = self._recv_packet(conn)
                if pkt is None:
                    break
                reply = self._handle(conn, pkt)
                _log("<-", repr(pkt[:40]), "->", repr(reply[:40]))
                self._send(conn, reply)
                if pkt in ("D", "k"):
                    break
        finally:
            conn.close()
            srv.close()


def udbserver(uc, port, start_pc=None, ready=None):
    """udbserver-compatible entry point (drop-in): serve GDB on `uc` at `port`.
    `ready` (a threading.Event) is set once the socket is listening."""
    GdbStub(uc, start_pc).serve(port, ready=ready)
