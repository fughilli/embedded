"""pyOCD probe type for CMSIS-DAP over elaphureLink (TCP), e.g. wireless-esp32-tools.

The wireless ESP32 DAP exposes CMSIS-DAP on TCP port 3240 using the elaphureLink
proxy protocol. Its other transport, USB/IP, has no usable client on macOS, so we
speak elaphureLink directly and reuse pyOCD's CMSIS-DAP stack on top of it.

Wire protocol (all handshake fields big-endian u32):
  host  -> probe: identifier 0x8a656c70, command 0 (handshake), proxy version
  probe -> host : identifier 0x8a656c70, command 0, DAP version
  then raw CMSIS-DAP command packets, each answered by one raw response packet.

The firmware hands each recv() to DAP_ExecuteCommand as one command, so two
pipelined commands coalesced into one TCP segment would lose the second. The
interface therefore pins the in-flight packet count to 1.

Probe IDs are ``elaphurelink:<host>[:<port>]``:
  pyocd commander -u elaphurelink:dap.local
  pyocd list -O elaphurelink.hosts=dap.local,probe-2.lan
"""

import logging
import select
import socket
import struct

from pyocd.core.options import OptionInfo, add_option_set
from pyocd.core.plugin import Plugin
from pyocd.core import session
from pyocd.probe.cmsis_dap_probe import CMSISDAPProbe
from pyocd.probe.pydapaccess.dap_access_api import DAPAccessIntf
from pyocd.probe.pydapaccess.dap_access_cmsis_dap import DAPAccessCMSISDAP
from pyocd.probe.pydapaccess.interface.interface import Interface

LOG = logging.getLogger(__name__)

PROBE_TYPE = "elaphurelink"
DEFAULT_PORT = 3240

EL_LINK_IDENTIFIER = 0x8A656C70
EL_COMMAND_HANDSHAKE = 0x00000000
EL_PROXY_VERSION = 0x00000001

CONNECT_TIMEOUT_S = 5.0
# Reachability check used when listing configured hosts.
LIST_TIMEOUT_S = 1.0
# Larger than any DAP_PACKET_SIZE the firmware reports (<= 512).
RECV_SIZE = 1500


def parse_address(address):
    """``host[:port]`` -> (host, port). Bracketed IPv6 (``[::1]:3240``) is accepted."""
    if address.startswith("["):
        host, _, rest = address[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
    elif address.count(":") == 1:
        host, port = address.split(":")
    else:
        host, port = address, ""
    if not host:
        raise ValueError(f"invalid elaphureLink address '{address}'")
    return host, int(port) if port else DEFAULT_PORT


def format_unique_id(host, port):
    if ":" in host:
        host = f"[{host}]"
    return f"{PROBE_TYPE}:{host}:{port}"


class ElaphureLinkInterface(Interface):
    """CMSIS-DAP packet transport over an elaphureLink TCP connection."""

    def __init__(self, host, port=DEFAULT_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self.vendor_name = "elaphureLink"
        self.product_name = "CMSIS-DAP"
        self.serial_number = format_unique_id(host, port)
        self.dap_version = None
        self._sock = None

    def open(self):
        try:
            sock = socket.create_connection((self.host, self.port), timeout=CONNECT_TIMEOUT_S)
        except OSError as exc:
            raise DAPAccessIntf.DeviceError(
                f"cannot connect to elaphureLink probe {self.host}:{self.port}: {exc}") from exc
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(struct.pack(">III", EL_LINK_IDENTIFIER, EL_COMMAND_HANDSHAKE, EL_PROXY_VERSION))
            reply = self._recv_exact(sock, 12)
            ident, command, self.dap_version = struct.unpack(">III", reply)
            if ident != EL_LINK_IDENTIFIER or command != EL_COMMAND_HANDSHAKE:
                raise DAPAccessIntf.DeviceError(
                    f"{self.host}:{self.port} is not an elaphureLink probe (bad handshake)")
            sock.settimeout(self.DEFAULT_USB_TIMEOUT_S)
        except OSError as exc:
            sock.close()
            raise DAPAccessIntf.DeviceError(
                f"elaphureLink handshake with {self.host}:{self.port} failed: {exc}") from exc
        except BaseException:
            sock.close()
            raise
        LOG.debug("elaphureLink %s:%d connected, DAP version %d", self.host, self.port, self.dap_version)
        self._sock = sock

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def write(self, data):
        try:
            self._sock.sendall(bytes(data))
        except OSError as exc:
            raise DAPAccessIntf.DeviceError(f"elaphureLink {self.host}:{self.port} write: {exc}") from exc

    def read(self):
        # One response per command, with one command in flight: everything that
        # arrives belongs to this response. Responses fit a single segment, but
        # take anything already queued in case the stack split it anyway.
        try:
            data = bytearray(self._sock.recv(RECV_SIZE))
            if not data:
                raise DAPAccessIntf.DeviceError(f"elaphureLink {self.host}:{self.port} closed the connection")
            while select.select([self._sock], [], [], 0)[0]:
                more = self._sock.recv(RECV_SIZE)
                if not more:
                    break
                data += more
        except socket.timeout:
            raise DAPAccessIntf.DeviceError(f"timeout reading from elaphureLink {self.host}:{self.port}") from None
        except OSError as exc:
            raise DAPAccessIntf.DeviceError(f"elaphureLink {self.host}:{self.port} read: {exc}") from exc
        return data

    def set_packet_count(self, count):
        # See module docstring: the firmware cannot frame pipelined commands.
        self.packet_count = 1

    @staticmethod
    def _recv_exact(sock, size):
        buf = bytearray()
        while len(buf) < size:
            chunk = sock.recv(size - len(buf))
            if not chunk:
                raise DAPAccessIntf.DeviceError("elaphureLink connection closed during handshake")
            buf += chunk
        return bytes(buf)


class ElaphureLinkProbe(CMSISDAPProbe):
    """CMSIS-DAP probe reached over elaphureLink."""

    @classmethod
    def from_address(cls, address):
        host, port = parse_address(address)
        return cls(DAPAccessCMSISDAP(None, interface=ElaphureLinkInterface(host, port)))

    @classmethod
    def get_all_connected_probes(cls, unique_id=None, is_explicit=False):
        if is_explicit and unique_id is not None:
            return [cls.from_address(unique_id)]
        return [cls.from_address(h) for h in _configured_hosts() if _is_reachable(h)]

    @classmethod
    def get_probe_with_id(cls, unique_id, is_explicit=False):
        return cls.from_address(unique_id) if is_explicit else None

    @property
    def description(self):
        return f"elaphureLink CMSIS-DAP ({self._link._interface.host})"


def _configured_hosts():
    sess = session.Session.get_current()
    value = sess.options.get(f"{PROBE_TYPE}.hosts") if sess is not None else None
    return [h.strip() for h in (value or "").split(",") if h.strip()]


def _is_reachable(address):
    try:
        host, port = parse_address(address)
        socket.create_connection((host, port), timeout=LIST_TIMEOUT_S).close()
        return True
    except (OSError, ValueError) as exc:
        LOG.debug("elaphureLink %s not reachable: %s", address, exc)
        return False


class ElaphureLinkProbePlugin(Plugin):
    """Plugin class, usable from a ``pyocd.probe`` entry point."""

    def load(self):
        return ElaphureLinkProbe

    @property
    def name(self):
        return PROBE_TYPE

    @property
    def description(self):
        return "CMSIS-DAP over elaphureLink TCP (e.g. wireless ESP32 DAP)"

    @property
    def options(self):
        return [
            OptionInfo(f"{PROBE_TYPE}.hosts", str, "",
                "Comma-separated elaphureLink probe addresses (host[:port]) to include when listing probes."),
        ]


def register():
    """Register the probe type without an entry point (e.g. in a Bazel runfiles tree)."""
    from pyocd.probe.aggregator import PROBE_CLASSES

    plugin = ElaphureLinkProbePlugin()
    PROBE_CLASSES.setdefault(plugin.name, plugin.load())
    add_option_set(plugin.options)
