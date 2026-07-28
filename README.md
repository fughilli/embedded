# Firmware monorepo — ESP32-C6 + ESP32 (WROOM) + RP2350 on Bazel

Bare-metal firmware built with **Bazel (bzlmod)** using native `cc_library` /
`cc_binary` rules. Cross toolchains, `picotool`/`esptool`, and Arduino core
sources are supplied by **Nix** (via `rules_nixpkgs`); Bazel drives the actual
compile/link. **Rust** modules link into the firmware via `rules_rust` with
bare-metal target triples.

Status: **All three boards build green.** RP2350 (Arm Cortex-M33) → `.uf2`;
ESP32-C6 (RISC-V rv32imac) and classic ESP32/WROOM (Xtensa LX6, dual core) →
`.bin`. RP2350 and ESP32-C6 link a `no_std` Rust module into the firmware; the
classic ESP32 substitutes a C++ fallback (upstream rustc has no Xtensa
backend — that needs the esp-rs fork). See `WORKLOG.md` for the build/verify
commands and the integration notes.

## Layout

| Path | What |
| --- | --- |
| `.claude-container-overlay/Dockerfile` | Installs Nix + Bazelisk (needs container relaunch) |
| `flake.nix`, `nix/` | Nix-provided toolchains + arduino-pico source; BUILD files exposing them |
| `MODULE.bazel` | bzlmod: rule sets, Nix repos, Rust triples, toolchain registration |
| `platforms/` | `board` constraint + `platform()` targets (rp2350, esp32c6, esp32) |
| `toolchains/cc/` | Reusable GCC-cross `cc_toolchain_config` + per-board `cc_toolchain` |
| `rules/embedded.bzl` | `embedded_binary` rule: platform transition wrapping a cc_binary |
| `rules/firmware.bzl` | `firmware_binary` rule: transition + package a cc_binary → board `.uf2`/`.bin` |
| `rules/arduino_library.bzl` | Repo rule: fetch a library `.zip`, code-generate its BUILD (FastLED uses it) |
| `libs/board/` | Board-support lib + the `arduino_core` facade, chosen by `select()` |
| `libs/pins/` | Per-board pin config (LED data pin via `select()`, `NUM_LEDS`) |
| `rust/blink_timing/` | no_std `rust_static_library` linked into the blink |
| `apps/blink/` | Blink firmware for both boards (GPIO + linked Rust) |
| `apps/rainbow/` | FastLED 64-LED rainbow chaser for both boards |

## Building (after the Nix overlay is in place)

```sh
# One-time: resolve the arduino-pico source hash (see WORKLOG step 3).
nix build .#arduino-pico

# RP2350 (Arm): ELF then flashable UF2
bazel build //apps/blink:rp2350               # blink.elf
bazel build //:blink_rp2350                    # blink.uf2  (alias)

# ESP32-C6 (RISC-V): ELF then flashable BIN
bazel build //:blink_esp32c6                   # blink.bin  (alias)

# Classic ESP32 / ESP32-WROOM (Xtensa LX6): flashable BIN
bazel build //:blink_esp32                     # blink.bin  (alias)

# FastLED rainbow chaser (64-LED strip) for any board
bazel build //:rainbow_rp2350 //:rainbow_esp32c6 //:rainbow_esp32
```

## Flashing a connected board

```sh
bazel run //apps/blink:flash_rp2350              # picotool load -x (board in BOOTSEL)
bazel run //apps/blink:flash_esp32c6             # esptool write-flash (bootloader+parts+app)
bazel run //apps/blink:flash_esp32c6 -- --port /dev/ttyACM0   # extra args pass through
bazel run //apps/blink:flash_esp32               # classic ESP32/WROOM (bootloader at 0x1000)
bazel run //apps/rainbow:flash_rp2350            # same targets exist for the rainbow app
```

Each `flash` target builds the firmware, then execs the Nix-provided tool over
the artifacts (rules in `rules/flash.bzl`).

## Rust ↔ C/C++ interop

Three mechanisms, demoed under `interop/`:

- **bindgen** (C headers → Rust FFI) — `rust_bindgen_library` from
  `rules_rust_bindgen`, with a Nix libclang toolchain (`//toolchains/bindgen`,
  so we don't compile LLVM from source). See `interop/bindgen`.
- **cbindgen** (Rust → C/C++ header) — `rust_cbindgen` (`rules/cbindgen.bzl`,
  Nix `cbindgen`). Used for real: the blink apps `#include` the generated
  `rust/blink_timing/blink_timing.h` instead of a hand-written `extern "C"`.
- **cxx** (safe C++ ↔ Rust) — the `cxx.rs` BCR module's `rust_cxx_bridge`. See
  `interop/cxx` (host-only: `cxx` uses `std`, so not for `no_std` firmware).

`bazel test //interop/...` exercises them.

Verify (no hardware): `picotool info blink.uf2` / `esptool image-info blink.bin`;
`*-size`/`nm` on the ELF (the Rust `blink_interval_ms` symbol should resolve).

The host needs only Bazelisk + Nix; everything else is hermetic. No board is
required — "done" is a valid `.elf`/`.uf2`, inspected with `arm-none-eabi-size`,
`objdump`, and `picotool info`.

## Design notes

- **`embedded_binary` + transition.** `apps/blink:rp2350` sets
  `//command_line_option:platforms` to `//platforms:rp2350` via an outgoing
  transition, so one `bazel build` retargets the whole subgraph — the cc/Rust
  toolchains resolve to the board and `select()`s pick the board's support code.
- **Nix supplies inputs, Bazel builds.** We do NOT run ESP-IDF/Pico-SDK CMake.
  RP2350 links a prebuilt `libpico.a` (shipped by arduino-pico) + its linker
  script; only the sketch + core are compiled. (ESP32-C6 will link prebuilt
  ESP-IDF `.a` blobs.)
- **Add a third-party Arduino library** with the `arduino` module extension
  (`rules/extensions.bzl`) — point it at a `.zip` and it code-generates a
  `cc_library`. **FastLED** is wired this way in `MODULE.bazel`; its generated
  library depends on `//libs/board:arduino_core` (the `select()` facade) so it
  compiles for whichever board the transition selects. The Arduino *cores*
  themselves come via Nix, not this rule.
- **`firmware_binary` rule** (`rules/firmware.bzl`) builds a board-agnostic
  `cc_binary` for a `board` (via an outgoing platform transition) and packages
  its flashable artifact (`.uf2` via picotool / `.bin` via esptool); the ELF is
  in the `elf` output group. It's a rule (not a macro) whose every label
  resolves in this module's repo, so it works from other modules unchanged — see
  `apps/blink` and `apps/rainbow`.

## Using this repo as a Bazel module

This repo is a bzlmod module named **`firmware`** (`module(name = "firmware")`).
It is not published to the Bazel Central Registry, so add it with an override:

```starlark
# consumer MODULE.bazel
bazel_dep(name = "firmware", version = "0.0.0")
git_override(
    module_name = "firmware",
    remote = "https://github.com/<you>/firmware.git",
    commit = "<sha>",
)
# or: archive_override(module_name="firmware", urls=[...], strip_prefix="...")
# or: local_path_override(module_name="firmware", path="../firmware")
```

**Prerequisite — Nix on the builder.** The cross toolchains, Arduino cores, and
`picotool`/`esptool` all come from Nix via `rules_nixpkgs`. Reuse this repo's
container overlay (`.claude-container-overlay/Dockerfile`) or install the
Determinate nix-installer; then `bazel build` pulls everything hermetically. The
host still needs only Bazelisk + Nix.

Depending on `firmware` gives you graph-wide, with no extra wiring:

- the registered **cc toolchains** (arm-none-eabi / riscv32-esp-elf /
  xtensa-esp-elf), the **Rust** bare-metal toolchains, and the **bindgen**
  toolchain;
- the board **platforms** `@firmware//platforms:rp2350`, `:esp32c6`, and
  `:esp32` (plus the `:is_rp2350` / `:is_esp32c6` / `:is_esp32`
  `config_setting`s).

You can also just build this repo's own targets from your workspace, e.g.
`bazel build @firmware//:rainbow_esp32c6`.

### Build your own firmware app

Write one board-agnostic `cc_binary` depending on the `@firmware//` **wrapper
targets** (they pull in the board-private Nix repos for you), then package + flash
it per board with `firmware_binary` and the flash rules — every label inside
those rules resolves in the `firmware` repo, so this just works:

```starlark
# consumer BUILD.bazel
load("@firmware//rules:firmware.bzl", "firmware_binary")
load("@firmware//rules:flash.bzl", "esptool_flash", "picotool_flash")

cc_binary(
    name = "app",
    srcs = ["app.cpp"],  # #include <Arduino.h>
    target_compatible_with = select({
        "@firmware//platforms:is_rp2350": [],
        "@firmware//platforms:is_esp32c6": [],
        "//conditions:default": ["@platforms//:incompatible"],
    }),
    deps = [
        "@firmware//libs/board:arduino_core",  # the board's Arduino core (provides main())
        # "@firmware//libs/pins",              # LED_DATA_PIN + NUM_LEDS, if useful
    ],
)

firmware_binary(name = "rp2350", binary = ":app", board = "rp2350")    # -> rp2350.uf2
firmware_binary(name = "esp32c6", binary = ":app", board = "esp32c6")  # -> esp32c6.bin

picotool_flash(name = "flash_rp2350", uf2 = ":rp2350")
esptool_flash(name = "flash_esp32c6", app = ":esp32c6")                # bootloader/parts default to firmware's
```

`bazel build //:rp2350` gives the flashable `.uf2`; `bazel build //:rp2350
--output_groups=elf` gives the raw `.elf`; `bazel run //:flash_esp32c6` flashes.

> **Why the wrappers?** `@arduino_pico`, `@arduino_esp32`, `@picotool`, `@fastled`,
> etc. are created by `firmware`'s module extensions and are **private to the
> `firmware` module** — bzlmod does not expose a module's extension repos to its
> consumers. Depend on the `@firmware//…` targets that wrap them
> (`//libs/board:arduino_core`, `//libs/pins`, `//apps/...`), whose internal deps
> resolve in `firmware`'s own repo mapping. The rules above default their tools
> (`@picotool`, `@esptool`, the esp32c6 bootloader/partitions) the same way.

### Reuse the individual rules

All loadable from `@firmware//`, and all use `firmware`-repo label defaults so
they work from a consumer without naming firmware's private repos:

| Load | Provides |
| --- | --- |
| `@firmware//rules:firmware.bzl` | `firmware_binary` (transition + package → `.uf2`/`.bin`) |
| `@firmware//rules:embedded.bzl` | `embedded_binary` (just the platform-transition → `.elf`) |
| `@firmware//rules:flash.bzl` | `esptool_flash` / `picotool_flash` |
| `@firmware//rules:cbindgen.bzl` | `rust_cbindgen` (Rust → C headers) |
| `@firmware//toolchains/cc:cc_toolchain_config.bzl` | the reusable GCC-cross `cc_toolchain_config` |

And the **`arduino`** module extension adds your own Arduino library from a
`.zip`, in your MODULE.bazel:

```starlark
arduino = use_extension("@firmware//rules:extensions.bzl", "arduino")
arduino.library(
    name = "my_lib",
    urls = ["https://.../my_lib-1.0.zip"],
    sha256 = "...",
    strip_prefix = "my_lib-1.0",
    deps = ["@firmware//libs/board:arduino_core"],
)
use_repo(arduino, "my_lib")
```
