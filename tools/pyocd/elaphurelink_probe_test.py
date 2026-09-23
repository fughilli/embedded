"""Hardware-free tests for elaphurelink_probe against a fake elaphureLink server.

`bazel test //tools/pyocd:elaphurelink_probe_test`
"""

import socket
import struct
import threading
import unittest

from pyocd.core.session import Session
from pyocd.probe.aggregator import DebugProbeAggregator
from pyocd.probe.debug_probe import DebugProbe

import elaphurelink_probe as el

DAP_INFO = 0x00
DAP_CONNECT = 0x02
INFO_PROTOCOL_VERSION = 0x04
INFO_CAPABILITIES = 0xF0
INFO_PACKET_COUNT = 0xFE
INFO_PACKET_SIZE = 0xFF


class FakeProbe:
    """elaphureLink server that, like the firmware, serves one client at a time and
    runs one command per recv(). pyOCD connects twice (board lookup, then open)."""

    def __init__(self, handshake_id=el.EL_LINK_IDENTIFIER, packet_count=8):
        self.handshake_id = handshake_id
        self.packet_count = packet_count
        self.commands = []
        self.pipelined = False
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def close(self):
        self.listener.close()
        self.thread.join(timeout=5)

    def _serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            with conn:
                self._serve_client(conn)

    def _serve_client(self, conn):
        hs = conn.recv(12)
        if len(hs) != 12 or struct.unpack(">III", hs)[0] != el.EL_LINK_IDENTIFIER:
            return
        conn.sendall(struct.pack(">III", self.handshake_id, el.EL_COMMAND_HANDSHAKE, 1))
        while True:
            data = conn.recv(1500)
            if not data:
                return
            self.commands.append(bytes(data))
            resp = self._execute(data)
            # The firmware would silently drop anything after the first command.
            if self._command_len(data) < len(data):
                self.pipelined = True
            conn.sendall(resp)

    @staticmethod
    def _command_len(data):
        return {DAP_INFO: 2, DAP_CONNECT: 2}.get(data[0], len(data))

    def _execute(self, data):
        if data[0] == DAP_INFO:
            info = data[1]
            if info == INFO_PACKET_COUNT:
                return bytes([DAP_INFO, 1, self.packet_count])
            if info == INFO_PACKET_SIZE:
                return bytes([DAP_INFO, 2]) + struct.pack("<H", 512)
            if info == INFO_CAPABILITIES:
                return bytes([DAP_INFO, 1, 0x03])  # SWD + JTAG
            if info == INFO_PROTOCOL_VERSION:
                version = b"1.2.0\0"
                return bytes([DAP_INFO, len(version)]) + version
            return bytes([DAP_INFO, 0])
        if data[0] == DAP_CONNECT:
            return bytes([DAP_CONNECT, data[1] or 1])
        return bytes([data[0], 0x00])  # DAP_OK


class ParseAddressTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(el.parse_address("dap.local"), ("dap.local", 3240))
        self.assertEqual(el.parse_address("10.0.0.2:4000"), ("10.0.0.2", 4000))
        self.assertEqual(el.parse_address("[fe80::1]:4000"), ("fe80::1", 4000))
        self.assertEqual(el.parse_address("fe80::1"), ("fe80::1", 3240))

    def test_unique_id_round_trips(self):
        uid = el.format_unique_id("dap.local", 3240)
        self.assertEqual(uid, "elaphurelink:dap.local:3240")
        self.assertEqual(el.parse_address(uid.split(":", 1)[1]), ("dap.local", 3240))


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeProbe()
        self.addCleanup(self.server.close)

    def test_open_identify_connect(self):
        probe = el.ElaphureLinkProbe.from_address(f"127.0.0.1:{self.server.port}")
        Session(probe, auto_open=False, no_config=True)  # attaches itself to the probe
        probe.open()
        try:
            self.assertIn(DebugProbe.Protocol.SWD, probe.supported_wire_protocols)
            self.assertIn(DebugProbe.Protocol.JTAG, probe.supported_wire_protocols)
            # Probe advertised 8 in-flight packets; the transport must pin it to 1.
            self.assertEqual(probe._link._interface.get_packet_count(), 1)
            probe.connect(DebugProbe.Protocol.SWD)
            self.assertEqual(probe.wire_protocol, DebugProbe.Protocol.SWD)
        finally:
            probe.close()
        self.assertFalse(self.server.pipelined, self.server.commands)
        self.assertIn(bytes([DAP_CONNECT, 1]), self.server.commands)

    def test_aggregator_resolves_explicit_uid(self):
        el.register()
        uid = f"elaphurelink:127.0.0.1:{self.server.port}"
        probes = DebugProbeAggregator.get_all_connected_probes(uid)
        self.assertEqual(len(probes), 1)
        self.assertIsInstance(probes[0], el.ElaphureLinkProbe)
        self.assertEqual(probes[0].unique_id, uid)


class HandshakeTest(unittest.TestCase):
    def test_rejects_non_elaphurelink_peer(self):
        server = FakeProbe(handshake_id=0xDEADBEEF)
        self.addCleanup(server.close)
        iface = el.ElaphureLinkInterface("127.0.0.1", server.port)
        with self.assertRaisesRegex(Exception, "bad handshake"):
            iface.open()

    def test_unreachable(self):
        sock = socket.create_server(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaisesRegex(Exception, "cannot connect"):
            el.ElaphureLinkInterface("127.0.0.1", port).open()


if __name__ == "__main__":
    unittest.main()
