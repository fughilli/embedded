# swd_bridge: Raspberry Pi 5 GPIO as a network CMSIS-DAP probe

`swd_bridge` bit-bangs SWD on two Pi 5 header GPIOs and serves the result as a
CMSIS-DAP probe over **elaphureLink** (TCP port 3240). The same protocol is spoken by
the wireless ESP32 DAP, so pyOCD reaches it through `//tools/pyocd`'s `elaphurelink`
probe type. The rest of the pyOCD tooling (`pyocd_flash`, `pyocd_debug`, commander,
gdbserver) works unchanged:

```sh
bazel run //tools/pyocd -- list -O elaphurelink.hosts=<pi-host>
bazel run //tools/pyocd -- commander -u elaphurelink:<pi-host> -t <target> -M attach
```

- DAP command handling is Arm's reference CMSIS-DAP firmware (`third_party/cmsis-dap`,
  Apache-2.0), compiled for Linux.
- `src/DAP_config.h` maps its pin hooks onto RP1 GPIO registers, mmapped from
  `/dev/gpiomem0`. No syscall per edge; each SWCLK edge waits for its posted PCIe
  write to land.
- SWD only (no JTAG or SWO). One command is in flight at a time, with 1 KiB packets.

## Wiring (defaults)

| Target | Pi 5 header |
|---|---|
| GND | pin 6 |
| SWCLK | pin 22 (GPIO25) |
| SWDIO | pin 18 (GPIO24), pad pull-up enabled |
| nRESET (optional) | any free GPIO, via `--nreset N` (open-drain emulated) |

Nothing else may drive these GPIOs. Between sessions the bridge leaves them high-Z,
and it restores their original pin function on exit.

## Build and run (on the Pi)

```sh
nix shell nixpkgs#gcc nixpkgs#gnumake -c make
sudo ./swd_bridge [--port 3240] [--swclk 25] [--swdio 24] [--nreset N]
```

It needs root (or access to `/dev/gpiomem0`). `default.nix` packages it for a NixOS
config. Bazel consumers can take the sources from `//tools/swd_bridge:sources`.

## Targets that remap their SWD pins

The bridge can only talk to a target whose SWD pins are still in debug mode. Firmware
that reuses or disables them (for example ArduPilot's default ESD protection, which
turns SWD into plain GPIO inputs shortly after boot) only allows attaching right
after reset, until that firmware option is changed.
