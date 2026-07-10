# Firmware monorepo — ESP32-C6 + RP2350 on Bazel

Bare-metal firmware built with **Bazel (bzlmod)** using native `cc_library` /
`cc_binary` rules. Cross toolchains, `picotool`/`esptool`, and Arduino core
sources are supplied by **Nix** (via `rules_nixpkgs`); Bazel drives the actual
compile/link. **Rust** modules link into the firmware via `rules_rust` with
bare-metal target triples.

Status: **Both boards build green.** RP2350 (Arm Cortex-M33) → `.uf2`; ESP32-C6
(RISC-V rv32imac) → `.bin`. Each links a `no_std` Rust module into the firmware.
See `WORKLOG.md` for the build/verify commands and the integration notes.

## Layout

| Path | What |
| --- | --- |
| `.claude-container-overlay/Dockerfile` | Installs Nix + Bazelisk (needs container relaunch) |
| `flake.nix`, `nix/` | Nix-provided toolchains + arduino-pico source; BUILD files exposing them |
| `MODULE.bazel` | bzlmod: rule sets, Nix repos, Rust triples, toolchain registration |
| `platforms/` | `board` constraint + `platform()` targets (rp2350, esp32c6) |
| `toolchains/cc/` | Reusable GCC-cross `cc_toolchain_config` + per-board `cc_toolchain` |
| `rules/embedded.bzl` | `embedded_binary` rule: platform transition wrapping a cc_binary |
| `rules/arduino_library.bzl` | Repo rule: fetch a library `.zip`, code-generate its BUILD |
| `libs/board/` | Board-support lib, implementation chosen by `select()` |
| `rust/blink_timing/` | no_std `rust_static_library` linked into the blink |
| `apps/blink/` | One blink firmware for both boards (board chosen by `select()`) |

## Building (after the Nix overlay is in place)

```sh
# One-time: resolve the arduino-pico source hash (see WORKLOG step 3).
nix build .#arduino-pico

# RP2350 (Arm): ELF then flashable UF2
bazel build //apps/blink:rp2350               # blink.elf
bazel build //:blink_rp2350                    # blink.uf2  (alias)

# ESP32-C6 (RISC-V): ELF then flashable BIN
bazel build //:blink_esp32c6                   # blink.bin  (alias)
```

## Flashing a connected board

```sh
bazel run //apps/blink:flash_rp2350              # picotool load -x (board in BOOTSEL)
bazel run //apps/blink:flash_esp32c6             # esptool write-flash (bootloader+parts+app)
bazel run //apps/blink:flash_esp32c6 -- --port /dev/ttyACM0   # extra args pass through
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
  `cc_library`. The arduino-pico *core* itself comes via Nix, not this rule.
