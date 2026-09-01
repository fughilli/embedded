"""App-local peripheral plugin — demonstrates extending the device model.

This lives in the *app* (a stand-in for a client repo), not in the shared sim
framework: it composes with the built-in //rules/sim/plugins/stm32g0:stm32g0_gpio
plugin to add a check the base model doesn't do. It watches RCC_IOPENR and records
whether the firmware enabled the GPIOD port clock (GPIODEN, bit 3) — proving a
client can model additional hardware without touching the base repo.
"""

from peripherals import Peripheral, sim_peripheral

RCC_BASE = 0x40021000
RCC_IOPENR = RCC_BASE + 0x34
GPIODEN = 3  # RCC_IOPENR bit 3


@sim_peripheral("blink.rcc_probe")
class RccProbe(Peripheral):
    def __init__(self):
        self.gpiod_clock_enabled = False

    def regions(self):
        return [(RCC_BASE, 0x400)]

    def write(self, uc, addr, size, value):
        if addr == RCC_IOPENR and (value & (1 << GPIODEN)):
            self.gpiod_clock_enabled = True
