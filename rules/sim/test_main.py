"""Entry point shared by every ``simulation_test`` target.

The ``simulation_test`` macro generates a ``py_test`` whose ``main`` is this file
and passes, as args, the rlocationpaths of the stub ELF + platform emu config, the
import name of the test's ``generator`` module, and the max_* limits. This module:

  1. resolves the ELF/emu-config out of runfiles,
  2. imports the generator module and finds its
     :class:`~stimulus.SimulationStimulusGenerator`,
  3. runs every stimulus through the Unicorn :mod:`harness`,
  4. optionally hands the live :class:`~harness.Simulator` to a ``srcs`` module's
     ``extra(sim)`` hook for tests that can't be expressed as a stimulus,
  5. prints a per-stimulus + peak report and exits non-zero if any stimulus
     failed or any max_* limit was exceeded.
"""

import argparse
import importlib
import inspect
import json
import sys

from python.runfiles import runfiles

import harness
from stimulus import SimulationStimulusGenerator


def _resolve(rf, rloc):
    path = rf.Rlocation(rloc)
    if not path:
        sys.exit("runfiles: could not resolve %r" % rloc)
    return path


def _find_generator(module):
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (issubclass(obj, SimulationStimulusGenerator) and
                obj is not SimulationStimulusGenerator and
                not inspect.isabstract(obj)):
            return obj()
    sys.exit("generator module %r defines no concrete "
             "SimulationStimulusGenerator subclass" % module.__name__)


def _check(name, value, limit, failures):
    if limit is not None and value > limit:
        failures.append("%s %d exceeds max %d" % (name, value, limit))
    flag = "" if (limit is None or value <= limit) else "  <-- OVER (max %d)" % limit
    print("  %-16s %8d%s" % (name, value, flag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--emu", required=True)
    ap.add_argument("--generator", required=True, help="import name of the generator module")
    ap.add_argument("--srcs", default="", help="import name of the extra-tests module")
    ap.add_argument("--max_cycles", type=int, default=None)
    ap.add_argument("--max_stack", type=int, default=None)
    ap.add_argument("--max_static", type=int, default=None)
    ap.add_argument("--max_dynamic", type=int, default=None)
    args = ap.parse_args()

    rf = runfiles.Create()
    elf_path = _resolve(rf, args.elf)
    with open(_resolve(rf, args.emu)) as f:
        emu = json.load(f)

    gen = _find_generator(importlib.import_module(args.generator))
    stimuli = list(gen.stimuli())

    sim = harness.Simulator(elf_path, emu)
    report = harness.SimReport()
    report.static_bytes = sim.static_bytes

    failures = []
    print("== stimuli ==")
    for i, stim in enumerate(stimuli):
        res = sim.run_stimulus(stim, i)
        report.results.append(res)
        report.peak_instructions = max(report.peak_instructions, res.instructions)
        report.peak_cycles = max(report.peak_cycles, res.cycles)
        report.peak_stack = max(report.peak_stack, sim.stack_used())
        report.peak_dynamic = max(report.peak_dynamic, sim.dynamic_used())

        status = "ok" if res.passed else "FAIL"
        expect = "" if stim.expected_return is None else " (want %d)" % stim.expected_return
        print("  [%s] %-18s ret=%-10d instrs=%-6d cyc=%-6d %s%s" %
              (status, stim.label(i), res.ret, res.instructions, res.cycles,
               "" if res.passed else "!!", expect))
        if not res.passed:
            failures.append("stimulus %s returned %d, expected %d" %
                            (stim.label(i), res.ret, stim.expected_return))

    # Optional non-stimulus test bodies.
    if args.srcs:
        mod = importlib.import_module(args.srcs)
        if hasattr(mod, "extra"):
            print("== extra (srcs) ==")
            try:
                mod.extra(sim)
            except AssertionError as e:
                failures.append("srcs.extra: %s" % e)

    print("== peaks vs limits ==")
    _check("cycles", report.peak_cycles, args.max_cycles, failures)
    _check("stack", report.peak_stack, args.max_stack, failures)
    _check("static", report.static_bytes, args.max_static, failures)
    _check("dynamic", report.peak_dynamic, args.max_dynamic, failures)

    if failures:
        print("\nFAILED (%d):" % len(failures))
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("\nPASS: %d stimuli, all limits within budget" % len(stimuli))


if __name__ == "__main__":
    main()
