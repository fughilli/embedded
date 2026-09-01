"""Virtual peripheral plugin system for full-app emulation.

A "device model" is a *composition of peripheral plugins*. Each plugin is a small
Python module (shipped by this repo or by a dependent repo) that defines one or
more :class:`Peripheral` subclasses and registers them with :func:`sim_peripheral`.
A ``simulation_app`` lists the plugins it wants; the harness imports each, then
instantiates every registered peripheral to form that app's device model.

This lets client projects that vendor this repo model whatever hardware they need
without touching it: they write their own plugin (depending only on this module),
declare it with ``sim_peripheral_plugin`` (see //rules/sim:sim.bzl), and add it to
``simulation_app(plugins=[...])``. Registration is keyed by name, so a client can
also *override* a built-in plugin's peripheral by registering the same name after
it (plugins import in the order listed).

A model owns one or more MMIO ranges (:meth:`regions`). The harness maps each range
as backing memory — so plain register reads/writes work for free — and installs
hooks so a model only implements registers with *side effects* (e.g. a GPIO BSRR
that updates ODR). :meth:`done` stops emulation once the app has shown enough to
judge (firmware main loops never return).
"""

import abc
import importlib

# name -> Peripheral subclass. Populated by @sim_peripheral as plugin modules are
# imported. Process-global: each test process imports only the plugins its target
# depends on, so the registry holds exactly that app's device model.
_REGISTRY = {}


def sim_peripheral(name):
    """Class decorator registering a Peripheral under a unique `name`
    (e.g. "stm32g0.gpio"). Re-registering a name overrides the earlier class."""
    def register(cls):
        cls.sim_name = name
        _REGISTRY[name] = cls
        return cls
    return register


def registered():
    """The current name -> class registry (a copy)."""
    return dict(_REGISTRY)


def import_plugins(module_names):
    """Import each plugin module so its @sim_peripheral registrations run."""
    for m in module_names:
        if m:
            importlib.import_module(m)


def instantiate(names=None):
    """Instantiate registered peripherals (all, or the named subset)."""
    reg = _REGISTRY if names is None else {n: _REGISTRY[n] for n in names}
    return [cls() for cls in reg.values()]


class Peripheral(abc.ABC):
    # Set by @sim_peripheral; lets a checker locate a model via result.by_name().
    sim_name = None

    @abc.abstractmethod
    def regions(self):
        """Iterable of (base, size) MMIO ranges this model owns."""
        raise NotImplementedError

    def read(self, uc, addr, size):
        """Called before a read in this model's range. Return an int to override
        the value, or None to let the backing memory answer. Default: backing."""
        return None

    def write(self, uc, addr, size, value):
        """Called after a write in this model's range (backing already updated).
        Implement register side effects here."""

    def done(self):
        """Return True once the app has exhibited enough behavior to judge; the
        harness then stops emulation. Default: never (rely on the cycle budget)."""
        return False
