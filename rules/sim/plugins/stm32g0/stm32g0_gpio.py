"""Reusable STM32G0 GPIO peripheral plugin (RM0444).

Ships with this repo as a built-in device-model plugin: any full-app emulation of
an STM32G0 target can compose it via
``simulation_app(plugins=["//rules/sim/plugins/stm32g0:stm32g0_gpio", ...])``.

Models the GPIOD port bank. The only register with a side effect is BSRR: writing
bit n sets ODR.n, bit n+16 resets it. We track the LED pin's level and log every
transition so a checker can assert the LED actually toggles, and stop emulation
once it has toggled enough (firmware blink loops never return).

Clients that need a different LED pin/port, or additional GPIO behavior, can
subclass this and re-register under the same name to override it, or ship their
own plugin alongside.
"""

from peripherals import Peripheral, sim_peripheral

GPIOD_BASE = 0x50000C00
GPIOD_ODR = GPIOD_BASE + 0x14
GPIOD_BSRR = GPIOD_BASE + 0x18
LED_PIN = 8  # PD8

# Stop after this many LED transitions (2 full on/off blinks) — enough to prove
# blinking without emulating minutes of busy-wait.
_STOP_AFTER_TOGGLES = 4


@sim_peripheral("stm32g0.gpio")
class Stm32g0Gpio(Peripheral):
    def __init__(self):
        self.led_state = 0
        self.transitions = []  # new states in order: [1, 0, 1, 0, ...]

    def regions(self):
        # The GPIO port bank (ports A..D within 0x50000000 + 0x2000).
        return [(0x50000000, 0x2000)]

    def write(self, uc, addr, size, value):
        if addr == GPIOD_BSRR:
            new = self.led_state
            if value & (1 << LED_PIN):          # BS8: set PD8
                new = 1
            if value & (1 << (LED_PIN + 16)):   # BR8: reset PD8
                new = 0
            if new != self.led_state:
                self.led_state = new
                self.transitions.append(new)
                uc.mem_write(GPIOD_ODR, (new << LED_PIN).to_bytes(4, "little"))

    def done(self):
        return len(self.transitions) >= _STOP_AFTER_TOGGLES
