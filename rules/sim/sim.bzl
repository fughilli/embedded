"""Bazel rules for executing firmware (and firmware snippets) under Unicorn.

Public API:

  simulation_platform(name, memory_map, architecture, timing_model=None)
      A device model. `memory_map` (JSON) is turned into a linker script + a GDB
      memory layout + a normalized emulator config; `architecture` picks the CPU
      (and the Bazel platform/toolchain the stub compiles under); `timing_model`
      (optional) is a profile that lets max_cycles be charged in virtual cycles
      instead of retired instructions. Provides SimulationPlatformInfo.

  simulation_stub(name, deps, platform, entry_point="_start")
      Links `deps` into a stub ELF for `platform` — under a transition to that
      platform's Bazel platform, so the sim cc_toolchain resolves and the
      generated linker script places sections at the modeled addresses. Provides
      SimulationStubInfo (the ELF + the platform's SimulationPlatformInfo).

  simulation_test(name, stub, generator, srcs=None, max_cycles, max_stack,
                  max_static, max_dynamic, generator_module="generator")
      Runs `generator`'s stimuli (and any `srcs` non-stimulus bodies) against the
      `stub` under Unicorn, failing if a stimulus mismatches or any max_* is
      exceeded. The platform/emulator config is inherited from the stub.

NOTE vs. the original sketch: simulation_test references a prebuilt
`simulation_stub` (the firmware-under-test) rather than re-deriving it, so the C
inputs live in one place and the platform flows stub -> test. Only ARMv8-M
(Cortex-M33) is wired up so far; add architectures to _ARCH below.
"""

load("@rules_python//python:defs.bzl", "py_binary", "py_test")

# The GDB the .debug targets launch. armv6-m/armv8-m stubs + firmware use the
# arm-none-eabi GDB from @arm_gcc; that's all we wire up so far.
_GDB = "@arm_gcc//:gdb"
_GDB_FILES = "@arm_gcc//:all"

def _debug_binary(name, mode, elf_target, emu_target, extra_args, extra_deps, extra_data):
    """A `<name>.debug` py_binary: brings up udbserver on the Unicorn engine and
    launches GDB attached to it, halted at the entry point."""
    py_binary(
        name = name,
        srcs = ["//rules/sim:sim_debug_main.py"],
        main = "//rules/sim:sim_debug_main.py",
        args = [
            "--mode=%s" % mode,
            "--elf=$(rlocationpath %s)" % elf_target,
            "--emu=$(rlocationpath %s)" % emu_target,
            "--gdb=$(rlocationpath %s)" % _GDB,
        ] + extra_args,
        data = [elf_target, emu_target, _GDB, _GDB_FILES] + extra_data,
        deps = [
            "//rules/sim:harness",
            "//rules/sim:peripherals",
            "//rules/sim:gdb_launch",
            "//rules/sim:uc_gdbserver",
            "@rules_python//python/runfiles",
        ] + extra_deps,
        tags = ["manual"],  # a bazel-run debug tool, not built by //...
    )

SimulationPlatformInfo = provider(
    doc = "A simulation device model: memory map + arch + generated build/runtime files.",
    fields = {
        "architecture": "CPU architecture string, e.g. 'armv8-m'.",
        "memory_map": "The source memory-map JSON File.",
        "linker_script": "Generated GNU ld script File (drives section placement).",
        "emu_config": "Generated normalized emulator config JSON File.",
        "gdb_layout": "Generated GDB memory-layout File.",
        "timing_model": "Optional timing-model JSON File, or None.",
        "bazel_platform": "Label of the Bazel platform() the stub compiles under.",
    },
)

SimulationStubInfo = provider(
    doc = "A firmware stub built for the emulator.",
    fields = {
        "elf": "The stub ELF File.",
        "platform": "The SimulationPlatformInfo it was built for.",
    },
)

# architecture -> the Bazel platform constraints its stubs compile under. The
# sim cc_toolchain (//toolchains/cc/*) resolves off exactly these.
_ARCH = {
    "armv8-m": struct(constraints = [
        "@platforms//cpu:armv8-m",
        "@platforms//os:none",
        "//platforms:sim_unicorn",
    ]),
    "armv6-m": struct(constraints = [
        "@platforms//cpu:armv6-m",
        "@platforms//os:none",
        "//platforms:sim_unicorn",
    ]),
}

# ---------------------------------------------------------------------------
# simulation_platform
# ---------------------------------------------------------------------------
def _simulation_platform_impl(ctx):
    ld = ctx.actions.declare_file(ctx.label.name + ".ld")
    emu = ctx.actions.declare_file(ctx.label.name + ".emu.json")
    gdb = ctx.actions.declare_file(ctx.label.name + ".gdb")

    args = ctx.actions.args()
    args.add("--memory_map", ctx.file.memory_map)
    args.add("--architecture", ctx.attr.architecture)
    args.add("--out_ld", ld)
    args.add("--out_emu", emu)
    args.add("--out_gdb", gdb)
    inputs = [ctx.file.memory_map]
    if ctx.file.timing_model:
        args.add("--timing_model", ctx.file.timing_model)
        inputs.append(ctx.file.timing_model)

    ctx.actions.run(
        executable = ctx.executable._gen,
        arguments = [args],
        inputs = inputs,
        outputs = [ld, emu, gdb],
        mnemonic = "SimGenPlatform",
        progress_message = "Generating sim platform %{label}",
    )

    return [
        # Default output = the linker script, so a stub can `-T$(location <plat>)`.
        DefaultInfo(files = depset([ld])),
        OutputGroupInfo(emu = depset([emu]), gdb = depset([gdb]), ld = depset([ld])),
        SimulationPlatformInfo(
            architecture = ctx.attr.architecture,
            memory_map = ctx.file.memory_map,
            linker_script = ld,
            emu_config = emu,
            gdb_layout = gdb,
            timing_model = ctx.file.timing_model,
            bazel_platform = ctx.attr.bazel_platform.label,
        ),
    ]

_simulation_platform = rule(
    implementation = _simulation_platform_impl,
    attrs = {
        "memory_map": attr.label(allow_single_file = [".json"], mandatory = True),
        "architecture": attr.string(mandatory = True),
        "timing_model": attr.label(allow_single_file = [".json"]),
        "bazel_platform": attr.label(mandatory = True),
        "_gen": attr.label(
            default = "//rules/sim:gen_platform",
            executable = True,
            cfg = "exec",
        ),
    },
)

def simulation_platform(name, memory_map, architecture, timing_model = None, **kwargs):
    if architecture not in _ARCH:
        fail("simulation_platform %r: unknown architecture %r (known: %s)" %
             (name, architecture, ", ".join(sorted(_ARCH))))
    visibility = kwargs.pop("visibility", None)

    # The concrete Bazel platform stubs for this arch transition to. Constraints
    # are identical across sim platforms of the same arch (same toolchain), so
    # this per-instance platform is just a stable, addressable label.
    native.platform(
        name = name + ".platform",
        constraint_values = _ARCH[architecture].constraints,
        visibility = visibility,
    )
    _simulation_platform(
        name = name,
        memory_map = memory_map,
        architecture = architecture,
        timing_model = timing_model,
        bazel_platform = ":" + name + ".platform",
        visibility = visibility,
        **kwargs
    )

# ---------------------------------------------------------------------------
# simulation_stub
# ---------------------------------------------------------------------------
def _platform_transition_impl(_settings, attr):
    return {"//command_line_option:platforms": [str(attr.bazel_platform)]}

_platform_transition = transition(
    implementation = _platform_transition_impl,
    inputs = [],
    outputs = ["//command_line_option:platforms"],
)

def _simulation_stub_impl(ctx):
    elf = ctx.actions.declare_file(ctx.label.name + ".elf")
    ctx.actions.symlink(
        output = elf,
        target_file = ctx.attr.binary[0][DefaultInfo].files_to_run.executable,
    )
    platform_info = ctx.attr.platform[SimulationPlatformInfo]
    return [
        DefaultInfo(files = depset([elf])),
        # Expose the platform's emu config so a simulation_test can pick it up
        # from the stub alone (the platform flows stub -> test).
        OutputGroupInfo(emu = depset([platform_info.emu_config])),
        SimulationStubInfo(elf = elf, platform = platform_info),
    ]

_simulation_stub = rule(
    implementation = _simulation_stub_impl,
    attrs = {
        "binary": attr.label(mandatory = True, cfg = _platform_transition),
        "platform": attr.label(mandatory = True, providers = [SimulationPlatformInfo]),
        # Read by _platform_transition to set --platforms. Kept separate from
        # `platform` (which carries the provider) because transitions can read
        # attributes but not providers.
        "bazel_platform": attr.label(mandatory = True),
        "entry_point": attr.string(default = "_start"),
        "_allowlist_function_transition": attr.label(
            default = "@bazel_tools//tools/allowlists/function_transition_allowlist",
        ),
    },
)

def simulation_stub(name, platform, deps = [], entry_point = "_start", **kwargs):
    visibility = kwargs.pop("visibility", None)
    linkopts = [
        "-T$(location %s)" % platform,
        "-Wl,-Map=%s.map" % name,
        "-Wl,--entry=%s" % entry_point,
        # A stub must keep EVERY function a stimulus might call, not just what the
        # entry reaches — so override the toolchain's --gc-sections. (Firmware
        # deps must be alwayslink so their objects are pulled into the link at
        # all; see simulation_stub's doc.)
        "-Wl,--no-gc-sections",
    ]
    native.cc_binary(
        name = name + "_bin",
        deps = deps + ["//rules/sim:sim_rt"],
        additional_linker_inputs = [platform],
        linkopts = linkopts,
        target_compatible_with = ["//platforms:sim_unicorn"],
        visibility = ["//visibility:private"],
        **kwargs
    )
    _simulation_stub(
        name = name,
        binary = ":" + name + "_bin",
        platform = platform,
        bazel_platform = platform + ".platform",
        entry_point = entry_point,
        visibility = visibility,
    )

# ---------------------------------------------------------------------------
# simulation_test
# ---------------------------------------------------------------------------
def simulation_test(
        name,
        stub,
        generator,
        srcs = None,
        max_cycles = None,
        max_stack = None,
        max_static = None,
        max_dynamic = None,
        generator_module = "generator",
        **kwargs):
    # Pull the platform's emu config out of the stub (single-file output group).
    native.filegroup(
        name = name + "_emu",
        srcs = [stub],
        output_group = "emu",
        visibility = ["//visibility:private"],
    )

    deps = [
        "//rules/sim:harness",
        "//rules/sim:stimulus",
        generator,
        "@rules_python//python/runfiles",
    ]
    args = [
        "--elf=$(rlocationpath %s)" % stub,
        "--emu=$(rlocationpath :%s_emu)" % name,
        "--generator=%s" % generator_module,
    ]
    data = [stub, ":" + name + "_emu"]

    if srcs:
        srcs_module = srcs.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
        if srcs_module.endswith(".py"):
            srcs_module = srcs_module[:-3]
        native.py_library(
            name = name + "_srcs",
            srcs = [srcs],
            imports = ["."],
            deps = ["//rules/sim:harness", "//rules/sim:stimulus"],
            visibility = ["//visibility:private"],
        )
        deps.append(":" + name + "_srcs")
        args.append("--srcs=%s" % srcs_module)

    for flag, val in (("max_cycles", max_cycles), ("max_stack", max_stack),
                      ("max_static", max_static), ("max_dynamic", max_dynamic)):
        if val != None:
            args.append("--%s=%d" % (flag, val))

    py_test(
        name = name,
        srcs = ["//rules/sim:test_main.py"],
        main = "//rules/sim:test_main.py",
        args = args,
        data = data,
        deps = deps,
        size = kwargs.pop("size", "small"),
        **kwargs
    )

    # <name>.debug: interactive GDB under the emulator, broken at the first
    # stimulus's entrypoint.
    _debug_binary(
        name = name + ".debug",
        mode = "test",
        elf_target = stub,
        emu_target = ":" + name + "_emu",
        extra_args = ["--generator=%s" % generator_module],
        extra_deps = [generator, "//rules/sim:stimulus"],
        extra_data = [],
    )

# ---------------------------------------------------------------------------
# Peripheral plugins — the device-model extension point
# ---------------------------------------------------------------------------
def _plugin_module(label):
    """The importable module name of a plugin = its target name (its source is
    <name>.py, imports=['.']). Works for '//pkg:name', ':name', and '//pkg'."""
    if label.startswith("@"):
        label = label.split("//", 1)[-1]
    if ":" in label:
        return label.split(":")[-1]
    return label.rsplit("/", 1)[-1]

def sim_peripheral_plugin(name, srcs = None, deps = [], **kwargs):
    """A reusable virtual-hardware plugin: a py_library whose module (named after
    the target, `<name>.py`) registers Peripheral models via @sim_peripheral.

    Ship these from this repo or from any dependent repo, then compose them in a
    `simulation_app(plugins=[...])`. Depends only on //rules/sim:peripherals, so a
    client repo can define hardware models without pulling in the whole harness.
    Module names share one namespace across an app, so name plugins uniquely
    (e.g. `stm32g0_gpio`, `acme_sensor`)."""
    native.py_library(
        name = name,
        srcs = srcs or [name + ".py"],
        imports = ["."],
        deps = deps + ["//rules/sim:peripherals"],
        **kwargs
    )

# ---------------------------------------------------------------------------
# simulation_app — full-app emulation of the EXACT device binary
# ---------------------------------------------------------------------------
def simulation_app(
        name,
        firmware,
        platform,
        plugins,
        checker = None,
        max_cycles = None,
        checker_module = "checker",
        **kwargs):
    """Boot the exact firmware ELF from `firmware` (a firmware_binary, whose `elf`
    output group is the image the device flashes) under Unicorn, from its reset
    vector, with a device model composed from `plugins` (a list of
    sim_peripheral_plugin targets) servicing MMIO. `checker` (a single py source
    with `check(result)`) asserts behavior. `platform` is a simulation_platform
    whose memory_map declares the RAM/flash + `kind: mmio` regions and
    `boot: reset`."""

    # The exact device image (elf output group of the firmware_binary) + the
    # platform's emu config (regions/mmio/boot), both pulled as single files.
    native.filegroup(
        name = name + "_elf",
        srcs = [firmware],
        output_group = "elf",
        visibility = ["//visibility:private"],
    )
    native.filegroup(
        name = name + "_emu",
        srcs = [platform],
        output_group = "emu",
        visibility = ["//visibility:private"],
    )

    deps = [
        "//rules/sim:harness",
        "//rules/sim:peripherals",
        "@rules_python//python/runfiles",
    ] + plugins
    args = [
        "--elf=$(rlocationpath :%s_elf)" % name,
        "--emu=$(rlocationpath :%s_emu)" % name,
        "--plugins=%s" % ",".join([_plugin_module(p) for p in plugins]),
    ]
    data = [":" + name + "_elf", ":" + name + "_emu"]

    if checker:
        native.py_library(
            name = name + "_checker",
            srcs = [checker],
            imports = ["."],
            deps = ["//rules/sim:peripherals"],
            visibility = ["//visibility:private"],
        )
        deps.append(":" + name + "_checker")
        args.append("--checker=%s" % checker_module)

    if max_cycles != None:
        args.append("--max_cycles=%d" % max_cycles)

    py_test(
        name = name,
        srcs = ["//rules/sim:app_main.py"],
        main = "//rules/sim:app_main.py",
        args = args,
        data = data,
        deps = deps,
        size = kwargs.pop("size", "medium"),
        **kwargs
    )

    # <name>.debug: interactive GDB under the emulator, broken at the app entry.
    _debug_binary(
        name = name + ".debug",
        mode = "app",
        elf_target = ":" + name + "_elf",
        emu_target = ":" + name + "_emu",
        extra_args = ["--plugins=%s" % ",".join([_plugin_module(p) for p in plugins])],
        extra_deps = plugins,
        extra_data = [],
    )
