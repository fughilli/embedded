"""The stimulus-generator contract a ``simulation_test``'s ``generator`` implements.

A stimulus is one emulated call: name a firmware function (``entrypoint``), give
its integer/pointer arguments, and (optionally) the value it must return. The
harness sets up the ARM calling convention, runs the function under Unicorn until
it returns, and — when ``expected_return`` is given — asserts the result.

Arguments and return values are plain integers (registers r0..r3 / r0). Pointer
arguments are modeled with :class:`Buffer`: the harness stages the bytes in the
stub's heap and passes the address in the register slot. This keeps the common
"call ``f(a, b)`` and check the result" case a one-liner while still allowing
tests that hand the firmware a buffer.
"""

import abc
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Union


@dataclass
class Buffer:
    """A pointer argument: `data` is staged in the stub heap; its address is
    passed in the register. After the call, `out_len` bytes are read back and
    exposed on the returned :class:`Result` for stimuli that produce output."""

    data: bytes
    out_len: int = 0


Arg = Union[int, Buffer]


@dataclass
class Stimulus:
    entrypoint: str
    args: List[Arg] = field(default_factory=list)
    expected_return: Optional[int] = None
    name: Optional[str] = None

    def label(self, index):
        base = self.name or self.entrypoint
        return "%s[%d]" % (base, index)


def call(entrypoint, *args, expected=None, name=None):
    """Convenience constructor: ``call("add", 2, 3, expected=5)``."""
    return Stimulus(entrypoint=entrypoint, args=list(args),
                    expected_return=expected, name=name)


class SimulationStimulusGenerator(abc.ABC):
    """Implemented by a test's ``generator`` py_library. ``stimuli`` yields the
    (entrypoint(args), return_value) pairs to drive through the emulator."""

    @abc.abstractmethod
    def stimuli(self) -> Iterable[Stimulus]:
        raise NotImplementedError
