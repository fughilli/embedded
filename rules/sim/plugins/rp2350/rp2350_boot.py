"""RP2350 (Cortex-M33) boot model — boots the exact arduino-pico image to loop().

The pico-sdk runtime_init touches a lot of hardware, and the RP2350 core has
custom coprocessors Unicorn's generic Cortex-M33 doesn't implement. This plugin
provides the validated model that gets the *exact* flashed image booting from its
reset vector all the way into the arduino loop(), blinking the LED:

  MMIO (read/write):
    * SIO CPUID (0xd0000000) reads 0                 -> core0 path
    * RESETS.RESET_DONE / PSM.DONE read all-ones     -> reset/power-on-state polls
    * XOSC.STATUS.STABLE, PLL_SYS/PLL_USB.CS.LOCK set -> oscillator/PLL lock polls
    * CLOCKS clk[].SELECTED = 1<<CTRL.SRC             -> clock-source-select polls
    * TIMER TIMELR/TIMEHR advance                     -> delay()/time_us_64()
    * the RP2350 atomic register aliases (SET/CLR/XOR at addr bits [13:12]) are
      emulated for the whole APB window (the SDK uses hw_set/clear_bits pervasively)
    * a bootrom lock word the ROM would set is seeded nonzero

  Code (attach):
    * rom_func_lookup() -> a no-op thumb stub (bootrom calls succeed without the ROM)
    * custom-coprocessor instructions (RCP/DCP integrity canaries) are skipped;
      the GPIO coprocessor `put` (mcrr p0,#4) is EMULATED to drive SIO GPIO — this
      is how gpio_put/digitalWrite reaches the LED on RP2350
    * WFE/WFI are no-ops (no interrupt delivery in this bring-up)

The LED (GPIO25 on a Pico2) toggling is observed and stops the run after a couple
of blinks. This is a bring-up model, not a cycle-accurate one; it exists to run the
real firmware far enough to exercise application logic.
"""

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

from peripherals import Peripheral, sim_peripheral

SIO = 0xD0000000
CPUID = SIO
RESET_DONE = 0x40020008
PSM_DONE = 0x4001800C
XOSC_STATUS = 0x40048004
PLL_SYS = 0x40050000
PLL_USB = 0x40058000
T0 = 0x400B0000
TIMEHR, TIMELR, TIMERAWH, TIMERAWL = T0 + 0x08, T0 + 0x0C, T0 + 0x24, T0 + 0x28
CLOCKS = 0x40010000
BOOTRAM_LOCK = 0x400E0828  # a lock word the real bootrom initializes
ROM_STUB = 0x10            # scratch in the (writable) bootrom region for a no-op

FLASH = 0x10000000
LED_PIN = 25               # Pico2 on-board LED
_STOP_AFTER_TOGGLES = 4

_R = ["UC_ARM_REG_R%d" % i for i in range(13)]


@sim_peripheral("rp2350.boot")
class Rp2350Boot(Peripheral):
    def __init__(self):
        self.reached = []
        self.led_state = 0
        self.transitions = []      # LED (GPIO25) states over time
        self._timer = 0
        self._latched = 0
        self._out = 0              # SIO GPIO output shadow
        import unicorn.arm_const as c
        self._reg = [getattr(c, n) for n in _R]

    # -- MMIO ---------------------------------------------------------------
    def regions(self):
        return [(0x40000000, 0x20000000), (SIO, 0x10000)]

    def read(self, uc, addr, size):
        if addr == CPUID:
            return 0
        if addr in (RESET_DONE, PSM_DONE):
            return 0xFFFFFFFF
        if addr == XOSC_STATUS:
            return 0x80000000
        if addr in (PLL_SYS, PLL_USB):
            return int.from_bytes(uc.mem_read(addr, 4), "little") | 0x80000000
        if addr in (TIMELR, TIMERAWL):
            self._latched = self._timer
            self._timer = (self._timer + 2000) & 0xFFFFFFFFFFFFFFFF
            return self._latched & 0xFFFFFFFF
        if addr in (TIMEHR, TIMERAWH):
            return (self._latched >> 32) & 0xFFFFFFFF
        if addr == BOOTRAM_LOCK:
            return 1
        return None

    def write(self, uc, addr, size, value):
        if 0x40000000 <= addr < 0x50000000:
            # RP2350 atomic register aliases: bits [13:12] select the op, the
            # real register is the address with those bits cleared.
            op = (addr >> 12) & 0x3
            reg = addr & ~0x3000
            cur = int.from_bytes(uc.mem_read(reg, 4), "little")
            new = {0: value, 1: cur ^ value, 2: cur | value, 3: cur & ~value}[op] & 0xFFFFFFFF
            uc.mem_write(reg, new.to_bytes(4, "little"))
            # CLOCKS clk[i]: SELECTED (ctrl+8) is a one-hot of the selected source.
            if CLOCKS <= reg < CLOCKS + 0x100 and (reg - CLOCKS) % 0xC == 0:
                uc.mem_write(reg + 8, (1 << (new & 0x3)).to_bytes(4, "little"))
        elif SIO + 0x10 <= addr <= SIO + 0x2C:  # direct SIO GPIO out (no aliases)
            o = addr - SIO
            if o == 0x10:
                self._out = value
            elif o == 0x18:
                self._out |= value
            elif o == 0x20:
                self._out &= ~value
            elif o == 0x28:
                self._out ^= value
            self._set_out(uc, self._out & 0xFFFFFFFF)

    # -- code (coprocessors, bootrom, milestones) ---------------------------
    def attach(self, uc, symbols):
        # Milestones (best-effort) so a checker can see how far boot got.
        for name in ("runtime_init", "xosc_init", "pll_init", "main", "setup", "loop"):
            if name in symbols:
                uc.hook_add(UC_HOOK_CODE, self._reach(name),
                            begin=symbols[name] & ~1, end=symbols[name] & ~1)
        # rom_func_lookup -> no-op stub.
        if "rom_func_lookup" in symbols:
            a = symbols["rom_func_lookup"] & ~1
            uc.hook_add(UC_HOOK_CODE, self._rom_lookup, begin=a, end=a)
        # Scan the loaded flash for custom-coprocessor + WFE/WFI instructions and
        # install targeted handlers (skip/emulate). Reading a generous span of
        # flash covers .text; hooks at non-code matches simply never fire.
        code = bytes(uc.mem_read(FLASH, 0x20000))
        for i in range(0, len(code) - 3, 2):
            hw1 = code[i] | (code[i + 1] << 8)
            hw2 = code[i + 2] | (code[i + 3] << 8)
            if (hw1 & 0xEC00) == 0xEC00 and ((hw2 >> 8) & 0xF) not in (10, 11):
                uc.hook_add(UC_HOOK_CODE, self._make_coproc(hw1, hw2),
                            begin=FLASH + i, end=FLASH + i)
            elif hw1 in (0xBF20, 0xBF30):  # wfe / wfi
                uc.hook_add(UC_HOOK_CODE, self._wfe, begin=FLASH + i, end=FLASH + i)

    def _make_coproc(self, hw1, hw2):
        is_mrc = (hw1 & 0xEF10) == 0xEE10
        dest = (hw2 >> 12) & 0xF if is_mrc else None
        # GPIO coprocessor put: mcrr p0,#4,Rt(gpio),Rt2(val),c0 -> drive the pin.
        is_gpio_put = (hw1 & 0xFFF0) == 0xEC40 and ((hw2 >> 8) & 0xF) == 0 and ((hw2 >> 4) & 0xF) == 4

        def hook(uc, addr, size, _ud):
            if is_gpio_put:
                pin = uc.reg_read(self._reg[(hw2 >> 12) & 0xF]) & 0x3F
                val = uc.reg_read(self._reg[hw1 & 0xF]) & 1
                out = (self._out | (1 << pin)) if val else (self._out & ~(1 << pin))
                self._set_out(uc, out & 0xFFFFFFFF)
            elif dest is not None and dest < 13:
                uc.reg_write(self._reg[dest], 0)
            uc.reg_write(UC_ARM_REG_PC, (addr + 4) | 1)  # skip (all coproc are 32-bit)
        return hook

    def _wfe(self, uc, addr, size, _ud):
        uc.reg_write(UC_ARM_REG_PC, (addr + 2) | 1)

    def _rom_lookup(self, uc, addr, size, _ud):
        uc.mem_write(ROM_STUB, b"\x00\x20\x70\x47")  # movs r0,#0 ; bx lr
        uc.reg_write(UC_ARM_REG_R0, ROM_STUB | 1)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def _reach(self, name):
        def hook(uc, addr, size, _ud):
            if name not in self.reached:
                self.reached.append(name)
        return hook

    def _set_out(self, uc, out):
        self._out = out
        led = (out >> LED_PIN) & 1
        if led != self.led_state:
            self.led_state = led
            self.transitions.append(led)
            if len(self.transitions) >= _STOP_AFTER_TOGGLES:
                uc.emu_stop()

    def done(self):
        return len(self.transitions) >= _STOP_AFTER_TOGGLES
