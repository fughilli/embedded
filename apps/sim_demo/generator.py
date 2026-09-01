"""Stimulus generator for the sim PoC: drives the snippet functions and asserts
their return values. One concrete SimulationStimulusGenerator; test_main finds it
by subclass."""

import struct

from stimulus import SimulationStimulusGenerator, call


def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _f2b(f):
    """float -> its 32-bit pattern (softfp passes floats in core registers)."""
    return struct.unpack("<I", struct.pack("<f", f))[0]


class Generator(SimulationStimulusGenerator):
    def stimuli(self):
        # sim_add
        yield call("sim_add", 20, 22, expected=42, name="add")
        yield call("sim_add", -5, 8, expected=3, name="add_neg")
        # sim_fib — recursion (stack + cycles)
        for n in (1, 5, 10):
            yield call("sim_fib", n, expected=_fib(n), name="fib%d" % n)
        # sim_alloc_sum — heap use; sum(0..n-1) = n*(n-1)/2
        for n in (4, 16, 64):
            yield call("sim_alloc_sum", n, expected=n * (n - 1) // 2,
                       name="alloc%d" % n)
        # sim_fpoly — hardware VFP. Args/return are float bit patterns (softfp).
        for x in (2.0, 3.5):
            yield call("sim_fpoly", _f2b(x),
                       expected=_f2b(x * x * 3.0 + x * 2.0 + 1.0),
                       name="fpoly_%g" % x)
