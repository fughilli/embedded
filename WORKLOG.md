# WORKLOG

Session handoff for a fresh agent with no memory of prior sessions. Read this
first, then `git log`. The plan lives at (approved) — this file supersedes it
with current state.

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
