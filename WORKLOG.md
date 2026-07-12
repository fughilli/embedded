# WORKLOG

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
