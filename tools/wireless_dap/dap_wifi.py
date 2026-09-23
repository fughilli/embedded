#!/usr/bin/env python3
"""Configure the wireless DAP's Wi-Fi over its serial console.

Talks to the `wt_console` REPL: every command ends with a single line starting
with "@OK" or "@ERR", which is picked out of the surrounding log output.

    dap_wifi.py -p /dev/cu.usbserial-10 status
    dap_wifi.py -p /dev/cu.usbserial-10 connect "My Network"      # prompts for password
    dap_wifi.py -p /dev/cu.usbserial-10 set "My Network" --restart  # save without trying now
    dap_wifi.py -p /dev/cu.usbserial-10 mode sta                     # disable the fallback AP
"""

import argparse
import getpass
import glob
import json
import re
import sys
import time

import serial

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Not anchored: some firmware debug printf()s lack a trailing newline, so the
# result can land at the end of an unrelated line.
RESULT_RE = re.compile(r"@(OK|ERR)(?: (.*))?$")


class ConsoleError(Exception):
    pass


def quote(arg):
    """Quote an argument for esp_console_split_argv."""
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'


def default_port():
    ports = sorted(glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.wchusbserial*")
                   + glob.glob("/dev/ttyUSB*"))
    return ports[0] if len(ports) == 1 else None


class Console:
    def __init__(self, port, baud=115200, verbose=False):
        self.verbose = verbose
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baud
        self.ser.timeout = 0.2
        # Keep EN and IO0 released so opening the port doesn't reset the chip
        # or hold it in the bootloader via the auto-reset circuit.
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()

    def close(self):
        self.ser.close()

    def sync(self, timeout=10.0):
        """Wait until the REPL shows its prompt.

        Some USB serial drivers (e.g. macOS CH34x) pulse DTR/RTS on open anyway,
        resetting the chip, so input sent before the REPL is up would be lost.
        """
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            self.ser.write(b"\n")
            end = time.monotonic() + 0.5
            while time.monotonic() < end:
                buf = (buf + self.ser.read(256))[-4096:]
                if b"dap>" in buf:
                    # Let any trailing boot logs drain before issuing a command.
                    time.sleep(0.3)
                    self.ser.reset_input_buffer()
                    return
        raise ConsoleError("no console prompt (is the wireless DAP firmware with serial console running?)")

    def command(self, *argv, timeout=5.0):
        line = " ".join([argv[0]] + [quote(a) for a in argv[1:]])
        self.sync()
        self.ser.write(line.encode() + b"\n")

        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            buf += self.ser.read(256)
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                text = ANSI_RE.sub("", raw.decode("utf-8", "replace")).strip("\r ")
                if self.verbose and text:
                    print(f"  | {text}", file=sys.stderr)
                if text.startswith(argv[0]):
                    continue  # echo of our own command line
                m = RESULT_RE.search(text)
                if not m:
                    continue
                if m.group(1) == "ERR":
                    raise ConsoleError(m.group(2) or "unknown error")
                return m.group(2) or ""
        raise ConsoleError(f"no response to '{argv[0]}' within {timeout:.0f}s")


def print_status(st):
    print(f"mode:       {st['mode']} (AP {'on' if st['ap_active'] else 'off'}, "
          f"STA {'on' if st['sta_active'] else 'off'})")
    print(f"sta mac:    {st['sta_mac']}")
    print(f"saved ssid: {st['saved_ssid'] if st['saved_ssid'] is not None else '(none)'}")
    if st["connected"] and st.get("ip") != "0.0.0.0":
        print(f"connected:  {st['ssid']} ({st['rssi']} dBm)")
        print(f"ip:         {st['ip']}  gw {st['gateway']}  mask {st['netmask']}")
    else:
        print("connected:  no")
    if "ap_ip" in st:
        print(f"ap ip:      {st['ap_ip']}")


def get_password(args):
    if args.password is not None:
        return args.password
    if args.open:
        return ""
    return getpass.getpass(f"Password for '{args.ssid}' (empty for open network): ")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-p", "--port", default=default_port(),
                        help="serial port (default: the only USB serial port found)")
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("-v", "--verbose", action="store_true", help="echo device output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="show Wi-Fi status")
    p.add_argument("--json", action="store_true", help="print raw JSON")
    p.add_argument("--wait", type=float, default=20,
                   help="seconds to wait for a saved network to connect (default 20)")

    for name, help_text in (("connect", "connect now; saved only if it succeeds"),
                            ("set", "save credential without connecting")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("ssid")
        p.add_argument("password", nargs="?",
                       help="passphrase (prompted if omitted; avoid putting it in shell history)")
        p.add_argument("--open", action="store_true", help="open network, no password")
        if name == "set":
            p.add_argument("--restart", action="store_true", help="restart to apply")

    p = sub.add_parser("mode", help="set persistent AP/STA mode")
    p.add_argument("mode", choices=["auto", "sta", "ap", "apsta"],
                   help="auto: AP only while not connected (default); sta: never start the AP")

    sub.add_parser("restart", help="restart the device")

    args = parser.parse_args()
    if not args.port:
        parser.error("could not pick a serial port, pass --port")

    con = Console(args.port, args.baud, args.verbose)
    try:
        if args.cmd == "status":
            # Opening the port may have reset the chip; give a saved network
            # time to come up rather than reporting a half-finished connect.
            deadline = time.monotonic() + args.wait
            while True:
                st = json.loads(con.command("wifi_status"))
                has_ip = st["connected"] and st.get("ip") != "0.0.0.0"
                if has_ip or st["saved_ssid"] is None or time.monotonic() > deadline:
                    break
                time.sleep(1)
            if args.json:
                print(json.dumps(st, indent=2))
            else:
                print_status(st)
        elif args.cmd == "connect":
            password = get_password(args)
            print(f"connecting to '{args.ssid}'...")
            print(con.command("wifi_connect", args.ssid, *([password] if password else []),
                              timeout=30))
        elif args.cmd == "set":
            password = get_password(args)
            print(con.command("wifi_set", args.ssid, *([password] if password else [])))
            if args.restart:
                print(con.command("restart"))
        elif args.cmd == "mode":
            print(con.command("wifi_mode", args.mode))
        elif args.cmd == "restart":
            print(con.command("restart"))
    except ConsoleError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
