# WORKLOG

## ✅ UNICORN SIM — DEVICE MODEL AS A PLUGIN SYSTEM (2026-09-01)

The virtual-peripheral device model is now a plugin registry so the client repos
that vendor this repo can extend it without modifying it.

- `//rules/sim:peripherals` gained a registry: `@sim_peripheral("name")` decorates
  a `Peripheral` subclass into `_REGISTRY`; `import_plugins()` / `instantiate()`
  compose a device model. Name-keyed, so a client can *override* a built-in by
  re-registering the same name (plugins import in listed order).
- `sim_peripheral_plugin(name, srcs=[<name>.py])` (sim.bzl) — a py_library whose
  module is the target name (imports=['.']), depending ONLY on
  //rules/sim:peripherals (no harness/unicorn), so a client repo can author
  hardware models cheaply. `simulation_app(..., plugins=[labels])` derives each
  module name from its label, imports all, and instantiates every registered
  peripheral as that app's device model. Checkers locate a model via
  `result.by_name(sim_name)`.
- Built-in shared plugin: `//rules/sim/plugins/stm32g0:stm32g0_gpio`
  ("stm32g0.gpio"). The blink test composes it with an APP-LOCAL plugin
  `//apps/blink_stm32g0b1:blink_rcc_probe` ("blink.rcc_probe") — the stand-in for
  a client extension — and the checker asserts both (LED blinks AND the GPIOD
  clock was enabled). Device model line in the run:
  `stm32g0.gpio(Stm32g0Gpio), blink.rcc_probe(RccProbe)`.
- Constraint: plugin module names share one flat namespace per app, so name them
  uniquely (`stm32g0_gpio`, `acme_sensor`), not `gpio`.

Client usage (from a repo vendoring this one):
    load("@firmware//rules/sim:sim.bzl", "sim_peripheral_plugin", "simulation_app")
    sim_peripheral_plugin(name = "acme_sensor", srcs = ["acme_sensor.py"])
    simulation_app(name = ..., firmware = ..., platform = ..., plugins = [
        "@firmware//rules/sim/plugins/stm32g0:stm32g0_gpio", ":acme_sensor"])

## ✅ UNICORN SIM — FULL-APP EMULATION MVP: blinky boots from reset (2026-09-01)

`bazel test //apps/blink_stm32g0b1:blink_sim` boots the **exact device image**
(the same ELF behind the flashed `.bin`, via the firmware_binary `elf` output
group) from its **reset vector** under Unicorn, runs it **unmodified** with
**virtual peripherals**, and asserts the LED (PD8) actually blinks (`[1,0,1,0]`).

Key findings + additions:
- **Unicorn 2.1.4 already emulates the Cortex-M33 FPU** (verified: `vmul.f32`/
  `vfma.f32` execute, IEEE-754 bit-exact) — NO patch/custom build needed. It
  doesn't even enforce the CPACR NOCP trap. Sim toolchain switched to hardware FP
  matching the RP2350 (`armv8-m.main+fp+dsp`, `fpv5-sp-d16`, softfp), harness sets
  CPACR best-effort.
- New **full-app mode**: `simulation_app(name, firmware, platform, peripherals,
  checker, max_cycles)` (sim.bzl) → `app_main.py`. Boots the real ELF from the
  vector table (SP/PC from `mem[vt]`, `mem[vt+4]`).
- **Virtual peripherals**: `Peripheral` ABC (`peripherals.py`: regions/read/write/
  done). The harness maps MMIO ranges as backing RAM (plain reads/writes just
  work) and installs read/write hooks for register side effects; a model's
  `done()` stops emulation (main loops never return). The STM32G0 model
  (`apps/blink_stm32g0b1/peripherals_model.py`) implements RCC + GPIOD BSRR→ODR
  and tracks PD8.
- `memory_map.json` gained `kind: mmio` regions + `boot: reset`; `gen_platform.py`
  emits them into `emu.json`. Harness gained `boot_app()` + armv6-m (Cortex-M0)
  in `_ARCH_CPU`.
- **Perf gotcha**: the per-instruction `UC_HOOK_CODE` counter throttles Unicorn to
  ~4M instr/s; a busy-wait blink half-period is ~15M instrs. App mode omits that
  hook → native speed, test runs in <1s.
- MVP scoping: `//apps/blink` (arduino, RP2350/ESP) is NOT MVP-able — booting it
  means emulating the whole arduino-pico/ESP-IDF runtime. The **bare-metal
  `//apps/blink_stm32g0b1`** (own Reset_Handler, `main()`, GPIO toggle, busy
  delay) was the tractable exact-binary target.

Three sim tests green: `//apps/sim_demo:demo_test`, `:demo_test_timed` (perf
stubs), `//apps/blink_stm32g0b1:blink_sim` (full app). `MODULE.bazel.lock` still
needs committing (added `@unicorn` + `@sim_pypi`).

## ✅ UNICORN FIRMWARE SIMULATOR — PoC GREEN (2026-09-01)

New ruleset `//rules/sim`: build firmware (and snippets) into a stub ELF for a
"simulation platform" and execute it under the Unicorn CPU emulator with
cycle/stack/static/heap budgets. `bazel test //apps/sim_demo:all` passes (2
tests, incl. a timing-model virtual-cycle variant).

Public API (`//rules/sim:sim.bzl`):
- `simulation_platform(name, memory_map, architecture, timing_model=None)` — a
  device model. `memory_map` JSON → GNU ld script + GDB memory layout +
  normalized `emu.json` (via `gen_platform.py`). `architecture` picks the Bazel
  platform/toolchain the stub compiles under; `timing_model` (optional) lets
  `max_cycles` be charged in virtual cycles instead of retired instructions.
  Provides `SimulationPlatformInfo`. Macro also emits `<name>.platform`
  (a `native.platform` with the arch constraints).
- `simulation_stub(name, deps, platform, entry_point="_start")` — links `deps`
  into `<name>.elf` under a transition to `<platform>.platform`, with the
  generated linker script wired in. Firmware `deps` must be `alwayslink=True`
  (stub links `--no-gc-sections` to keep every callable entrypoint). Provides
  `SimulationStubInfo`.
- `simulation_test(name, stub, generator, srcs=None, max_cycles, max_stack,
  max_static, max_dynamic, generator_module="generator")` — runs `generator`'s
  stimuli (`(entrypoint(args), expected_return)` pairs from a
  `SimulationStimulusGenerator` ABC) + any non-stimulus `srcs` bodies against
  `stub` under Unicorn; fails on mismatch or any exceeded budget. NOTE vs. the
  original sketch: takes a prebuilt `stub` (the sketch didn't say where the C
  came from); platform/emu flows stub→test.

Unicorn wiring: the pip `unicorn` bindings' native lib is overridden by Nix —
`@unicorn` (nixpkgs `unicorn` 2.1.4) staged + selected via `LIBUNICORN_PATH`
(the loader probes `$LIBUNICORN_PATH/libunicorn.so.2` first). Mirrors the
`//tools/pyocd` libusb pattern. Dedicated pip hub `@sim_pypi`
(unicorn==2.1.4 + pyelftools), lock at `//rules/sim:requirements.lock`
(`bazel run //rules/sim:requirements.update`).

Target: Cortex-M33 / ARMv8-M only so far (`//platforms:sim_armv8m`, new
constraint `//platforms:sim_unicorn`; `//toolchains/cc/sim_armv8m` reuses
`@arm_gcc`, no `--gc-sections`). Add arches to `_ARCH` in sim.bzl.

Harness (`harness.py`): loads the ELF by VMA (so `.data` is initialized and
`.bss` zeroed without running reset), maps regions per `emu.json`, calls each
function with `LR = sentinel(0x90000000)|1` to detect return, counts retired
instructions via `UC_HOOK_CODE`, and scans per-word stack/heap canaries for
peak usage. `sim_rt.c` supplies a bump `malloc` over the linker `.sim_heap`
region + `_start`. Two gotchas that cost cycles: (1) must `_reset_memory()`
(replay PT_LOAD segments) before each stimulus or the heap bump pointer leaks
and `max_dynamic` becomes cumulative; (2) a bare `ASSERT(...)` /
`_sim_stack_limit=` must sit at linker-script TOP LEVEL, not inside `SECTIONS`.

`MODULE.bazel.lock` changed (added `@unicorn` + `@sim_pypi`) — commit it.

## ✅ CMSIS DEVICE FAMILY PACKS VENDORED FOR pyOCD (2026-09-01)

A pyOCD `--target` outside its built-ins (the STM32G0B1 → `stm32g0b1rctx`, an
STM32G0B1RCT6) needs a CMSIS Device Family Pack. Rather than a stateful
`pyocd pack install` into `~/.cache`, packs are vendored hermetically via a new
ruleset (`rules/cmsis_pack.bzl`) that mirrors the pip lockfile flow:

- `tools/pyocd/packs.in` (targets, one/line) → `bazel run //tools/pyocd:update_packs`
  → `tools/pyocd/packs.lock` (JSON: per-pack url+sha256). The generator
  (`update_packs.py`) resolves each target → pack via `cmsis_pack_manager`'s
  index (the same index `pyocd pack find` uses), derives the pack URL from the
  pack PDSC's `<url>`, downloads + hashes it. Verified: the generated lock is
  byte-identical to the hand-checked seed (Keil.STM32G0xx_DFP 2.1.0).
- The `cmsis_packs` module extension `json.decode`s the lock and creates **one
  `@cmsis_pack_<slug>` repo per pack** (http download, sha256-pinned) + a
  `@cmsis_packs` hub that symlinks them all under `packs/`. //tools/pyocd depends
  on `@cmsis_packs//:all_packs` (runfiles) and `cmsis_pack_inject.py` auto-adds
  `--pack <file>` for each to pack-aware subcommands (flash/list/erase/...).
- Result: `bazel run //tools/pyocd -- list --targets --source pack` shows
  `stm32g0b1rctx` (43 G0B1 parts) with NO manual pack install — proven on Linux.

Gotcha that cost a debug cycle: locating the packs in runfiles by splitting the
module path on `/_main/` picked the wrong root — the **execroot** path itself
contains `/_main/` (`.../execroot/_main/bazel-out/.../X.runfiles/_main/...`).
Anchor on `.runfiles/` instead. Also: the STM32G0B1RCT6 is 256K Flash / 144K
SRAM, so the demo variant is now `stm32g0b1` = (256K, 144K, `stm32g0b1rctx`).

## ✅ pyOCD VENDORED AS A HERMETIC FLASH DRIVER (2026-08-31)

`//tools/pyocd` — pyOCD brought in via Bazel's Python mechanism (first use of
rules_python in this repo), for flashing targets without ROM DFU (the STM32G0B1,
any CMSIS-DAP/ST-Link chip). Split cleanly:

- **Python deps from PyPI** via `rules_python` (1.5.4 — the 1.x line; 2.x needs
  Bazel >=8 and we're on 7.7.1). `pip.parse(hub_name="pypi")` consumes
  `tools/pyocd/requirements.lock`, a UNIVERSAL lock resolved by `uv` via
  `rules_uv` (`pip_compile(universal=True)`; `bazel run
  //tools/pyocd:requirements.update`). Universal (not pip-tools) is load-bearing:
  pyOCD needs `hidapi` only off-Linux (`; platform_system != "Linux"`), so a
  single-platform lock omits it and the macOS build fails to find `@pypi//hidapi`
  — the universal lock carries it with a `sys_platform != 'linux'` marker. pyocd's
  native deps (capstone, cmsis-pack-manager) ship aarch64 + x86_64 manylinux
  wheels, so no from-source compiles. Interpreter is rules_python's hermetic 3.11.
- **libusb from Nix, NOT the wheel.** pyOCD's one native C lib is libusb; the
  `libusb-package` wheel bundles a prebuilt blob. Instead `@libusb`
  (nixpkgs `libusb1`) is materialized like esptool/picotool, and the wrapper
  `py_library //tools/pyocd:nix_libusb` stages the lib (`.so` on Linux /
  `.dylib` on macOS, selected in `//nix:libusb.BUILD`) next to `nix_backend.py`
  (via the `stage_nix_libs` genrule, fixed name) and points pyusb's
  `find_library` at it. (No Nix hidapi: pyOCD uses libusb for HID on Linux and
  the pip `hidapi` wheel elsewhere.) Verified hardware-free:
  `bazel run //tools/pyocd:verify_backend` asserts `find_library('usb-1.0')` and
  the live `usb.backend.libusb1` backend both resolve to the staged Nix lib.
- **Wiring gotcha:** pyusb finds libusb via `ctypes.util.find_library`, which
  ignores `LD_LIBRARY_PATH` and preloaded objects (it shells ldconfig/gcc) — so
  a bare preload leaves pyusb with "no backend". The fix is to patch
  `find_library` (globally + `usb.libloader`) to return the staged path; a
  RTLD_GLOBAL preload alone is insufficient. nix_backend.py resolves the `.so`
  by `__file__`-relative path (staged under a fixed soname), avoiding the
  unstable canonical Nix repo name in runfiles.
- **`pyocd_flash`** (rules/flash.bzl) wraps the py_binary: execs it via
  rlocation, staging its runfiles (hermetic interpreter + wheels + Nix libusb)
  alongside the firmware_binary's ELF. Wired at
  `//apps/blink_stm32g0b1:flash_stm32g0b1` (target `stm32g0b1xx`; needs a
  one-time `pyocd pack install stm32g0b1`).
- **In-container caveat:** `pyocd list`/`flash` block inside libusb device
  enumeration (`usb/backend/libusb1.py:enumerate_devices`) because the container
  has no debug probe / usbfs — expected. Reaching that libusb call IS the proof
  the Nix libusb is wired; completion needs real hardware.

## ✅ STM32G0 FAMILY (CORTEX-M0+) BUILDS GREEN (2026-08-31)

`bazel build //:blink_stm32g0b1` → valid STM32G0B1 image. Fourth board added
end-to-end, generalized to the whole **G0 family**: platform + constraint
(`armv6-m` / os:none / `stm32g0_board`), one Cortex-M0+ cc_toolchain, bare-metal
board support, a blink app, and a `firmware_binary` packager branch
(`objcopy -O binary` → raw `.bin` for pyOCD/st-flash/dfu at 0x08000000). NOT run
on hardware — verified via the ELF: `objdump -f` = architecture `armv6s-m`, entry
`0x08000199` (Reset_Handler|thumb), and the G0B1 memory map takes effect —
vector[0] / `_estack` = `0x20024000` (SP = RAM top = 0x20000000 + 144K);
`board_setup`/`board_set_led`/`main` all resolve.

The whole G0 line (G031…G0B1/G0C1) shares ONE toolchain + board support; a part
differs only in its linker memory map and pyOCD target. Both live in
`//libs/board/stm32g0:stm32g0.bzl` (`STM32G0_VARIANTS` table +
`stm32g0_linker_script` macro, which stamps `stm32g0.ld.tpl` via
`expand_template`). Adding a part is a one-line table entry; the demo instantiates
**STM32G0B1** (NUCLEO-G0B1RE, 512K Flash / 144K SRAM).

What made STM32 different from the Arduino boards (for the next bare-metal chip):

- **No Arduino core — fully freestanding.** The STM32 has no wired Arduino core,
  so it does NOT go through the `//libs/board:arduino_core` facade. It links its
  own startup (`//libs/board/stm32g0/startup_stm32g0.c`: vector table +
  `Reset_Handler`, following the G0B1/G0C1 category-5 IRQ layout — the family
  superset) and a generated linker script (Flash @0x08000000, SRAM @0x20000000)
  instead. Added a header-only `//libs/board:board_hdr` (board.h, no core dep).
- **Reuses @arm_gcc** (same arm-none-eabi GCC as the RP2350) — no new Nix dep to
  build. The toolchain differs only in `-mcpu=cortex-m0plus -mthumb
  -mfloat-abi=soft` (no FPU on armv6-m) and bare-metal link flags
  (`--specs=nano.specs --specs=nosys.specs -nostartfiles -Wl,--gc-sections`).
- **Walk `.init_array` by hand, not `__libc_init_array`.** With `-nostartfiles`,
  newlib's `__libc_init_array` pulls in `_init`/`_fini` from crti/crtn (omitted),
  and v6-m's `_init` trips a "dangerous relocation: unsupported relocation".
  Reset_Handler iterates `__preinit_array_*`/`__init_array_*` directly instead.
- **The linker script is wired at the app**, not the toolchain: `//apps/blink_stm32g0b1`
  generates its `.ld` (`stm32g0_linker_script`) and passes `-T$(location :g0b1_ld)`
  via `linkopts` + `additional_linker_inputs` (a family-generic toolchain can't
  hardcode one memory map).
- Demo LED is on **PD8**, driven by raw RCC/GPIO register access (RM0444; the
  register map is identical family-wide). The port/pin are three `LED_*` defines
  in `board_stm32g0.c` (port base + IOPENR clock bit + pin). `board_delay_ms` is
  a coarse HSI-16MHz busy-wait, not timer-accurate.

## ✅ CLASSIC ESP32 / WROOM (XTENSA) BUILDS GREEN (2026-07-17, session 6)

`bazel build //:blink_esp32 //:rainbow_esp32` → valid ESP32 images (esptool
image-info: chip ESP32, DIO/80m/4MB, entry 0x400819a8; blink text 207K).
Third board (`esp32`) added end-to-end: platform + constraint, xtensa
cc_toolchain, per-chip SDK slice + core targets, flash targets. All C6/RP2350
targets rebuilt green alongside. NOT yet run on hardware — flash script
verified only for correct chip/offsets (0x1000 bootloader, 0x8000 partitions,
0xe000 boot_app0, 0x10000 app).

What made the xtensa wiring different from the C6 (for the next chip):

- **Toolchain selection is -mdynconfig, not -march/-mcpu.** The unified
  `xtensa-esp-elf` tarball (same esp-14.2.0_20260121 release as the riscv one)
  ships per-chip wrapper binaries `xtensa-esp32-elf-*` that bake in
  `-mdynconfig=xtensa_esp32.so`; `nix/xtensa_gcc.BUILD` points at those, so no
  arch flag is needed anywhere. Arch quirk flags that DO matter (from
  `flags/c_flags`): `-mlongcalls -mdisable-hardware-atomics
  -mfix-esp32-psram-cache-issue -mfix-esp32-psram-cache-strategy=memw`.
- **@arduino_esp32 is now per-chip**: sdk/esp32 merged alongside sdk/esp32c6
  (nix/arduino_esp32_drv.nix), `*_esp32`-suffixed targets in
  arduino_esp32.BUILD (include list generated from `sdk/esp32/flags/includes`,
  minus 2 entries that don't exist on disk). Extra SDK archives live in `ld/`
  again (libphy.a, librtc.a, libbtdm_app.a).
- **No upstream Rust for Xtensa** (esp-rs fork only). `//apps/blink` select()s
  `//rust/blink_timing:blink_timing_fallback` (C++, same cbindgen header/ABI)
  on `is_esp32`; the cbindgen header target itself is host-generated and
  board-independent, so it stays a common dep.
- Classic-ESP32 facts: bootloader offset **0x1000** (C6 is 0x0); IDE defaults
  QIO/80MHz → memory-type dir `qio_qspi`, image headers still DIO (same
  ROM-boots-DIO remap as the C6); no native USB → `ARDUINO_USB_CDC_ON_BOOT=0`,
  no `ARDUINO_USB_MODE`; Serial is UART0; variant defines no LED_BUILTIN
  (libs/board/esp32.cpp uses GPIO 2, the usual devkit LED).
- Hash TODOs in nix/esp_xtensa_gcc.nix: x86_64-linux and aarch64-darwin are
  fakeHash placeholders (aarch64-linux is real); fill on first use.

## ✅ ESP32-C6 WIFI AP + WEBSERVER ON HARDWARE (2026-07-12, session 5)

`bazel run //apps/wifi_ap:flash_esp32c6`: soft-AP (`esp32c6-hello`) with a
WebServer serving a static page at http://192.168.4.1/ — verified end-to-end
with ping + curl from a laptop joined to the AP. New in this session:

- `nix/arduino_esp32.BUILD`: cc_library targets for the bundled Arduino
  libraries `network`, `fs`, `wifi`, `hash`, `webserver` (same `_CXX_COPTS` as
  the core; deps mirror their #includes — WebServer needs `hash` for
  SHA1Builder.h, that's the only non-obvious edge).
- `//rules:resources.bzl` `c_resource_library`: codegen (resource_gen.py)
  that embeds resource files as NUL-terminated C const char arrays + header,
  so pages live in real .html files. The wifi_ap page is now a styled color
  picker webapp driving the onboard WS2812 via `/led?c=RRGGBB` ->
  `rgbLedWrite`.

Debugging traps burned into memory the hard way (nothing was actually broken):

- **Phones with mobile data enabled route around a no-internet AP** and time
  out loading the page, while laptops work fine. Test AP webservers with a
  laptop, or disable mobile data / accept the "no internet — stay connected?"
  prompt on the phone.
- **On-device loopback TCP self-connect (to the AP's own IP) does not work**
  in this lwIP port — fails identically on an Arduino-IDE-built control
  binary. It is NOT evidence of a broken listener; don't chase it.
- Control experiments via `arduino-cli` (brew-installed; uses the same
  ~/Library/Arduino15 cores as the IDE) are cheap and decisive for "is it my
  build system or the environment": same sketch, known-good toolchain, same
  hardware. FQBN gotcha: add `:CDCOnBoot=cdc` or Serial goes to UART0 pins.

## ✅ ESP32-C6 RAINBOW RUNS ON HARDWARE (2026-07-11, session 4)

`bazel run //apps/rainbow:flash_esp32c6` now produces a rainbow on the devkit's
GPIO8 WS2812. Three stacked bugs meant no Bazel-built image had ever actually
booted on the C6 (an old Arduino-IDE bootloader at 0x0 kept running whatever it
found, masking everything):

1. **Bootloader offset**: `esptool_flash` wrote the bootloader at 0x1000
   (ESP32/S2 convention). The C6 ROM loads from **0x0** (`rules/flash.bzl`).
2. **QIO vs DIO image headers**: we stamped QIO into image headers; the C6 ROM
   boots in DIO and firmware upgrades to quad I/O itself. Symptom:
   `ets_loader.c 67` + TG0 watchdog boot loop. arduino-esp32 does the same
   remap (`FlashMode.qio.build.flash_mode=dio` in boards.txt). Now: `elf2image
   --flash_mode dio` for bootloader + app images, and `write-flash
   --flash-mode keep` so esptool doesn't re-stamp the header at 0x0.
3. **Stale partition table**: the repo's shipped `tools/partitions/default.bin`
   is ancient — old layout, no trailing MD5 row, which IDF ≥5 requires
   (`load_partitions returned 0x105` → assert in `esp_ota_get_running_partition`
   → reboot loop). Now generated from `default.csv` via `gen_esp32part.py`,
   like the IDE does (`nix/arduino_esp32.BUILD`).

Also: `nix/esp_riscv_gcc.nix` now selects the toolchain tarball by host
platform (was hardcoded aarch64-linux + autoPatchelfHook, which fails on
macOS; autoPatchelf/zlib deps are now Linux-only). x86_64-linux hash is still
a fakeHash placeholder — fill in on first use.

Debugging notes for next time:
- USB-Serial/JTAG re-enumerates on reset, so one-shot boot logs are easy to
  miss; a scratch app that prints its probe result every second in `loop()`
  beats chasing the boot log. `rmt_new_tx_channel`+`rmt_enable` on the LED pin
  is a good FastLED-equivalent probe.
- Read-back + `esptool image-info`/`cmp` against the built artifact tells you
  what's REALLY on the chip; "Hash of data verified" only means the write
  landed, not that anything boots it.
- Known-good reference: Arduino IDE cache (`~/Library/Caches/arduino/sketches`)
  keeps `build.options.json`, `compile_commands.json`, and the exact
  bootloader/partition bins it flashed — ideal for diffing configs.

## ✅✅ BOTH MILESTONES COMPLETE (2026-07-10, session 3)

Both firmwares build green from one `bazel` invocation each:

- `bazel build //:blink_rp2350` → `blink.uf2` (RP2350 Arm, picotool: rp2350-arm-s)
- `bazel build //apps/blink_esp32c6:blink_bin` → `blink.bin` (esptool image-info:
  valid ESP32-C6 image, chip ID 13, flash 4MB/80m/QIO). ELF: RISC-V, soft-float,
  entry 0x40800828, text 227K/data 73K/bss 204K. Rust `blink_interval_ms` linked
  (C↔Rust proven on RISC-V too), alongside `app_main`.

The ESP32-C6 wiring that worked (for future reference):
- Toolchain: Espressif prebuilt `riscv32-esp-elf-14.2.0_20260121` fetched
  directly + autoPatchelf'd (`nix/esp_riscv_gcc.nix`) — do NOT use the
  nixpkgs-esp-dev flake (it evaluates all of ESP-IDF, GBs — that's what filled
  the disk and forced the session-2→3 restart).
- Core + SDK merged into ONE nix tree (`nix/arduino_esp32_drv.nix`, SDK at
  sdk/esp32c6) so a single Bazel repo owns both → no cross-repo include/-L pain.
- `nix/arduino_esp32.BUILD` (generated): 318 sdk includes + variant/core as
  native `includes`/`defines` attrs (propagate to the app); per-language std
  (split `core_c`/`core_cpp`, both `alwayslink` to fix intra-core link order);
  link = build-time `-L` genrule + the shipped `@ld_flags/@ld_scripts/@ld_libs`
  response files in a `--start-group` with the SDK archives.
- Gotcha: `libphy.a`/`libbtbb.a` live in `sdk/esp32c6/ld/` (not `lib/`) — staged
  via the `sdk_libs` glob; `-L ld` already covers them.
- esptool 5.x from nixpkgs; `elf2image` accepts the underscore flags.

Everything committed. Historical session-2/3 notes retained below.

---

## (historical) 2026-07-10 session 3 — ESP32-C6 start + read-only /tmp incident

The `nix flake show github:mirrexagon/nixpkgs-esp-dev` evaluated
`esp-idf-full`/`esp-idf-riscv` and pulled GBs, filling the disk and flipping
`/tmp/claude-501/...` read-only (blocked Bash until a restart). Avoided by using
the direct fetchurl toolchain approach. Facts captured at the time:

### ESP32-C6 facts (no re-research needed)

- **arduino-esp32 3.3.10** source (no submodules needed for core):
  `fetchFromGitHub espressif/arduino-esp32 rev=3.3.10`
  hash `sha256-C4yinBEB+J/RwRDPpE3lhQ65DcXicVNLJnynWhftPDc=`
- **RISC-V toolchain** (matches the libs — fetch this exact one, autoPatchelf'd):
  `https://github.com/espressif/crosstool-NG/releases/download/esp-14.2.0_20260121/riscv32-esp-elf-14.2.0_20260121-aarch64-linux-gnu.tar.gz`
  (binaries prefixed `riscv32-esp-elf-`; gcc 14.2.0)
- **esp32-arduino-libs** (prebuilt IDF `.a` + `ld/` + `flags/*` + sdkconfig, host-agnostic):
  `https://github.com/espressif/esp32-arduino-lib-builder/releases/download/idf-release_v5.5/esp32-arduino-libs-idf-release_v5.5-73550728-v6.zip`
  — the esp32c6 SDK dir is `esp32c6/` inside; use `fetchzip` (hash via fakeHash).
- **esptool**: nixpkgs `esptool` (4.9.x) via `nix_pkg.attr` (simple).
- RISC-V flags (esp32c6): `-march=rv32imac_zicsr_zifencei -mabi=ilp32`. Rust
  triple `riscv32imac-unknown-none-elf` (already registered in MODULE.bazel).
- **NOT yet read** (do first after restart): arduino-esp32 `platform.txt` esp32c6
  `recipe.c.combine` + the `@{sdk}/flags/{defines,includes,c_flags,cpp_flags,
  ld_flags,ld_scripts,ld_libs}` response files. The esp32 build passes these as
  `@file` args; compile/link read `-I`/`-L` paths RELATIVE to the sdk dir, so
  they likely need `-iprefix {sdk}/` (like arduino-pico's includes) or running
  with cwd=sdk. This is the main iteration surface (expect the same kind of
  multi-round debugging as RP2350). elf→bin: `esptool --chip esp32c6 elf2image`.

### Plan after restart (Milestone 2)

**Already drafted this session (files on disk, uncommitted, UNTESTED):**
`nix/esp_riscv_gcc.nix`, `nix/esp32_arduino_libs.nix`, `nix/arduino_esp32_drv.nix`,
`nix/arduino_esp32.nix`, `nix/riscv_gcc.BUILD`, `nix/esptool.BUILD`,
`toolchains/cc/esp32c6/BUILD.bazel`, `libs/board/esp32c6.cpp` (real impl),
`apps/blink_esp32c6/{blink.cpp,BUILD.bazel}` (draft), `nix/arduino_esp32.BUILD`
(placeholder filegroup only), `nix/BUILD.bazel` exports updated.

**Still TODO (needs Bash):**
1. `export PATH="$HOME/.local/bin:$PATH"`. If nix missing, the overlay symlinks it
   into /usr/local/bin — should just work.
2. Resolve fakeHash placeholders: `nix build .#...` for the riscv gcc tarball +
   esp32-arduino-libs zip (add flake `packages` outputs or use nix-prefetch).
3. Wire MODULE.bazel: `nix_pkg.file` for riscv_gcc / arduino_esp32 /
   esp32_arduino_libs (attrs from nix/arduino_esp32.nix), `nix_pkg.attr` esptool,
   `use_repo`, and `register_toolchains("//toolchains/cc/esp32c6:cc_toolchain")`.
4. Read arduino-esp32 `platform.txt` (esp32c6 recipe.c.combine) + esp32c6
   `flags/*` response files; write the real `nix/arduino_esp32.BUILD`
   cc_library(core) + cross-repo cc_import of @esp32_arduino_libs sdk libs/ld.
   (autoPatchelf on the gcc + the response-file include model are the likely
   iteration pain points.)
5. Update `libs/board/BUILD` esp32c6 select branch to dep `@arduino_esp32//:core`.
6. Build + verify: `bazel build //apps/blink_esp32c6:blink_bin`;
   `esptool image-info blink.bin`; riscv nm shows blink_interval_ms.

NOTE: `//apps/blink_esp32c6` + libs/board esp32c6 branch reference repos not yet
in MODULE.bazel, so `bazel build //...` will error until wired — build
`//:blink_rp2350` specifically (still green).

---

Session handoff for a fresh agent with no memory of prior sessions. Read this
first, then `git log`. The plan lives at (approved) — this file supersedes it
with current state.

## ✅ Milestone 1 COMPLETE (2026-07-10, session 2)

`bazel build //:blink_rp2350` produces a valid RP2350 firmware:
- `bazel-bin/apps/blink_rp2350/blink.elf` — ARM ELF32, soft-float ABI, entry in
  flash; `text 614K / data 12K / bss 3.8K`.
- `bazel-bin/apps/blink_rp2350/blink.uf2` — picotool reports family
  `rp2350-arm-s`, chip RP2350, image type "ARM Secure".
- The `no_std` Rust symbol `blink_interval_ms` links into the ELF (C↔Rust proven).

Build/verify commands (remember `export PATH="$HOME/.local/bin:$PATH"` for nix):
```
bazel build //:blink_rp2350
nix shell nixpkgs#gcc-arm-embedded -c arm-none-eabi-size bazel-bin/apps/blink_rp2350/blink.elf
nix shell nixpkgs#picotool -c picotool info bazel-bin/apps/blink_rp2350/blink.uf2
```

### Key things learned wiring arduino-pico into native Bazel (for Milestone 2)
- pico-sdk ships its own BUILD.bazel → strip Bazel markers in the nix derivation
  so the tree is one package (else globs can't cross the package boundary).
- The nix source tree is store symlinks; globs work, but package markers block them.
- Relative-include wrapper sources: `cores/rp2040/api/*.cpp` include
  `ArduinoCore-API/api/*.cpp` (→ textual_hdrs); `sdkoverride/*` and `lwip/*`
  include SDK `.c` by relative path (→ excluded; libs already prebuilt).
- Full define set matters (platform_def.txt x2 + boards.txt ~90 defines);
  `PICO_CYW43_ARCH_HEADER`, `__DYNAMIC_REENT__`, `NO_USB`/`DISABLE_USB_SERIAL`.
- memmap_default.ld is a template → genrule substitutes region sizes (simplesub).
- Link recipe: `--undefined=` runtime-init list + syscall stubs
  (newlib_interface.o), `--wrap` response files, `--start-group` with the
  prebuilt libs + `-lm -lc -lstdc++ -lc`.
- **ABI: use the SOFT-float Rust triple `thumbv8m.main-none-eabi`** — eabihf
  (hard-float) won't link with arduino-pico's softfp objects.
- cc_toolchain_config needs `target_libc` + an explicit `archiver_flags` feature
  (else `ar` runs with no args). Transition rules no longer take the
  `_allowlist_function_transitions` attr in this Bazel.

---

## Where we are (2026-07-10, session 2 — post-relaunch, actively building)

Overlay landed: Bazelisk + Nix work. Bootstrapping is DONE and the build is
being iterated to green. Concrete progress this session:

- **Nix on PATH fixed.** The overlay's `rm -rf per-user` dangled the `default`
  profile that `ENV PATH` relied on. Fixed the overlay (appended a block
  symlinking Determinate Nix bins into `/usr/local/bin`) so future relaunches
  are clean. If nix is ever missing again: `find /nix/store -maxdepth 2 -type d
  -name bin -path '*determinate-nix*'` and put it on PATH.
- **nixpkgs pin fixed.** `nixos-25.11` is a *branch*, so `tag=` 404'd on the
  refs/tags URL. MODULE.bazel now pins `commit = b6018f87…` (25.11 HEAD).
- **arduino-pico hash resolved.** `rev = 5.6.1`,
  `hash = sha256-Ul+Ft9Gewkiio/Y28ECycfF3TfVUUt6fezbjcNMLykw=` in
  nix/arduino_pico_drv.nix.
- **Toolchains VALIDATED.** `bazel build //rust/blink_timing --config=rp2350`
  succeeded — `@arm_gcc` fetched via Nix, `thumbv8m` rust-std resolved, and both
  cc + rust toolchains bind to `//platforms:rp2350`. (Also fixed a real bug: a
  constraint_value and platform can't share a name → constraints are now
  `*_board`, platforms are bare names.)
- **arduino_pico.BUILD is now FAITHFUL**, transcribed from the repo's own
  platform_{inc,def,wrap}.txt / core_{inc,wrap}.txt / boards.txt / platform.txt:
  83 include dirs, real defines (F_CPU=125MHz, PICO_PLATFORM=rp2350-arm-s, …),
  and the full link recipe (the critical `--undefined=` runtime-init list, the
  `--wrap` response files passed via `@file`, `--script=memmap_default.ld`, and
  the `--start-group … libpico.a liblwip.a libbearssl.a ota.o -lm -lc -lstdc++
  -lc --end-group`). Toolchain no longer forces -ffreestanding/-nostartfiles
  (arduino-pico uses neither).

**Current step:** compiling `@arduino_pico//:core` for rp2350, iterating on any
remaining missing-header/define errors, then linking `//apps/blink_rp2350:blink`
and producing the `.uf2`.

Original (pre-relaunch) scaffolding notes are retained below for reference.

## FIRST: relaunch to get the overlay

The overlay (`.claude-container-overlay/Dockerfile`) installs Bazelisk (aarch64)
and Determinate Nix. It is applied by the launcher on the next
`claude-container` start (~30s first rebuild, cached after). After relaunch,
sanity-check:

```sh
nix --version
bazel version           # should honor .bazelversion (7.7.1)
```

## Bootstrap order (post-relaunch)

1. **Resolve the arduino-pico source hash.** `nix/arduino_pico_drv.nix` pins
   `earlephilhower/arduino-pico` with a **placeholder** `hash = lib.fakeHash`
   and `rev = "4.6.0"`. First:
   - Verify `rev` is a real, current release tag (check the repo's tags).
   - `nix build .#arduino-pico` → it fails printing the correct `got: sha256-…`.
     Paste that into `hash`. Re-run until it builds.
2. **First Bazel build.** `bazel build //apps/blink_rp2350:blink`. Expect to
   iterate — see "Known iteration surfaces" below. Then `bazel build
   //:blink_rp2350` for the `.uf2`.
3. **Verify (no hardware):** `arm-none-eabi-size`, `arm-none-eabi-objdump -d`
   (confirm `blink_interval_ms` from Rust is present + resolved — proves C↔Rust
   link), `picotool info blink.uf2` (expect family `rp2350-arm-s`).

## Verified facts (don't re-research)

- BCR pins (checked 2026-07-10): `rules_cc` 0.2.22, `platforms` 1.1.0,
  `bazel_skylib` 1.9.0, `rules_pkg` 1.2.0, `rules_rust` 0.71.3,
  `rules_nixpkgs_core` 0.13.0. `rules_nixpkgs_cc` is **NOT on the BCR** — we
  don't use it (we hand-roll the cc_toolchain).
- rules_nixpkgs bzlmod API: `nix_repo` @ `//extensions:repository.bzl`
  (`.github`/`.file`/…); `nix_pkg` @ `//extensions:package.bzl`
  (`.attr`/`.file`, attrs `attr`/`repo`/`build_file`). Used in MODULE.bazel.
- rules_rust triple→constraint mapping (source-verified @ 0.71.3):
  `thumbv8m.main-none-eabihf` → `[@platforms//cpu:armv8-m, @platforms//os:none]`
  (armv8-m IS the Cortex-M33 profile and DOES exist in platforms 1.1.0);
  `riscv32imac-unknown-none-elf` → `[@platforms//cpu:riscv32, @platforms//os:none]`.
  Our `//platforms:rp2350` carries exactly `armv8-m` + `os:none` (+ our `board`
  value), so both cc AND rust toolchains resolve. Rust registration is manual:
  `register_toolchains("@rust_toolchains//:all")` (in MODULE.bazel). ✓
- RP2350 Arm flags (arduino-pico boards.txt): `-mcpu=cortex-m33 -mthumb
  -march=armv8-m.main+fp+dsp -mfloat-abi=softfp -mfpu=fpv5-sp-d16 -mcmse`
  (softfp, NOT hardfloat). In `toolchains/cc/rp2350_arm/BUILD.bazel`.
- arduino-pico ships prebuilt `lib/rp2350/{libpico.a,liblwip.a,libbearssl.a,
  memmap_default.ld}`; crt0/bootrom/vectors live inside libpico.a. UF2 via
  `picotool uf2 convert … --family rp2350-arm-s`.

## Known iteration surfaces (expected to need fixing on first build)

1. **`nix/arduino_pico.BUILD` — includes/defines/wrap list (THE main work).**
   The include dirs, `defines`, and `-Wl,--wrap=` list are STARTER sets. Transcribe
   the real values from the extracted repo's
   `lib/rp2350/platform_inc.txt` / `platform_def.txt` / `platform_wrap.txt` and
   `boards.txt` (rpipico2 stanza). Cross-check against `arduino-cli compile
   --verbose` for a blink sketch. Many pico-sdk `**/include` dirs are missing.
2. **`cxx_builtin_include_directories`** (`toolchains/cc/cc_toolchain_config.bzl`)
   is set to `/nix/store` (loose, suppresses "undeclared inclusion" broadly).
   Optionally tighten to the compiler's actual reported dirs
   (`arm-none-eabi-gcc -E -Wp,-v -xc++ /dev/null`).
3. **cc_toolchain tool resolution.** We reference Nix tools as Files
   (`@arm_gcc//:gcc` etc.) via `tool(tool=…)` in action_configs — cross-repo
   safe. If Bazel complains about a missing tool for some action, add an
   `action_config` for it in `cc_toolchain_config.bzl`.
4. **`nix_pkg.file` semantics for arduino_pico.** Confirm `@arduino_pico`
   materializes the source tree with our `arduino_pico.BUILD` on top. If the
   `attr`/`file` handling differs from expectation, the alternative is a
   `http_archive` on an arduino-pico release zip + the same BUILD.
5. **nixpkgs attr names.** `gcc-arm-embedded` and `picotool` are the expected
   nixpkgs attributes; if resolution fails, check exact names in the pinned
   channel (`nix search nixpkgs picotool`).
6. **Rust no_std link.** We build `rust_static_library` with `-Cpanic=abort`.
   If the link fails on `eh_personality`/std mismatch, revisit panic strategy /
   whether prebuilt `rust-std` for thumbv8m is compatible.

## Open risks

- **RP2350 softfp vs Rust `eabihf` ABI.** arduino-pico + our cc_toolchain are
  **softfp**; the Rust triple `thumbv8m.main-none-eabihf` is **hard-float ABI**.
  The final C+Rust link may fail on FP-ABI mismatch. If so, options: (a) switch
  the Rust side to a soft-float configuration, (b) confirm the eabihf/softfp
  object interop is actually accepted for these translation units (the Rust code
  uses no floats, so it may link cleanly regardless). Prove with a tiny link
  before assuming. This is called out in MODULE.bazel + the toolchain BUILD.
- **nixpkgs pin reproducibility.** `nix_repo.github(tag="nixos-25.11")` has no
  `sha256` yet (add after first fetch). Keep it in sync with flake.nix's input.

## Milestone 2 — ESP32-C6 (not started)

Plan (from research, ready to execute): add `mirrexagon/nixpkgs-esp-dev` as a
flake input → expose `riscv32-esp-elf` gcc + `esptool` via `nix_pkg` (keep the
flake's patchelf/FHS wrapping) → vendor `espressif/esp32-arduino-libs/esp32c6`
(prebuilt `.a` + `ld/` + `flags/*` + frozen `sdkconfig`, treated read-only) →
add an esp32c6 `cc_toolchain` (reuse `cc_toolchain_config`, flags
`-march=rv32imac_zicsr_zifencei -mabi=ilp32`) → transcribe the order-sensitive
`recipe.c.combine` link line from arduino-esp32 `platform.txt` into the app's
link → fill in `libs/board/esp32c6.cpp` → `esptool … elf2image` genrule for
`.bin`. Uncomment the esp32c6 `register_toolchains` line in MODULE.bazel.

## Task list

See the harness task list (#1–#8). #1–#7 done (scaffolding); #8 (docs+commit) in
progress. All remaining real work is post-relaunch iteration, tracked above.
