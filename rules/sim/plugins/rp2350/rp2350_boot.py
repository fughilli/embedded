"""RP2350 (Cortex-M33) boot-bring-up peripheral plugin.

Booting the *exact* arduino-pico image from reset needs a handful of things the
pico-sdk runtime_init touches before main(). This plugin provides the validated
"basic set":

  * SIO CPUID (0xd0000000) reads 0            -> the reset handler takes the core0
                                                 path (non-zero => spin in bootrom)
  * rom_func_lookup() intercepted             -> returns a no-op thumb stub, so the
                                                 SDK's bootrom calls (reset/locking)
                                                 succeed without emulating the 32KB
                                                 mask ROM
  * permissive APB status reads (0xFFFFFFFF)  -> LOCK/STABLE/ENABLE polls pass
  * CLOCKS "SELECTED" reads (0x40010000+) = 1 -> the clock-source-select polls pass

With these, the image boots from the vector table through runtime_init ->
xosc_init -> pll_init (clock init) under the emulator. It records boot milestones
(by hooking their symbols) so a checker can assert how far it got, and watches SIO
GPIO output for the eventual LED.

KNOWN LIMIT: reaching setup()/loop() additionally needs a faithful CLOCKS/PLL
model (the per-generator SELECTED one-hot must echo 1<<source, not a constant),
plus a TIMER time source for delay(). That clock-tree model is the next step;
this plugin gets the app booting and its runtime_init running.
"""

from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

from peripherals import Peripheral, sim_peripheral

SIO_BASE = 0xD0000000
SIO_CPUID = 0xD0000000
CLOCKS_BASE = 0x40010000
CLOCKS_END = 0x40011000
# Where we stage the no-op ROM stub (in the writable/executable BOOTROM region).
ROM_STUB = 0x00000010  # bytes: movs r0,#0 ; bx lr

# Boot milestones we hook (best-effort; only those present in the ELF are used).
_MILESTONES = ("runtime_init", "xosc_init", "pll_init", "main", "setup", "loop")
# Stop once we've reached this far (the furthest reliably-reachable point today).
_STOP_AT = "pll_init"


@sim_peripheral("rp2350.boot")
class Rp2350Boot(Peripheral):
    def __init__(self):
        self.reached = []          # milestone symbols hit, in order
        self.gpio_writes = 0       # SIO GPIO output register writes (future LED)

    def regions(self):
        # APB/AHB peripheral window + SIO. (Flash/SRAM/bootrom/PPB are plain memory
        # mapped by the platform; the SDK's VTOR write to PPB just lands in RAM.)
        return [(0x40000000, 0x20000000), (SIO_BASE, 0x10000)]

    def read(self, uc, addr, size):
        if addr == SIO_CPUID:
            return 0                          # core 0
        if SIO_BASE <= addr < SIO_BASE + 0x10000:
            return 0                          # other SIO regs: benign default
        if CLOCKS_BASE <= addr < CLOCKS_END:
            return 1                          # clock-source SELECTED polls (== 1)
        if 0x40000000 <= addr < 0x60000000:
            return 0xFFFFFFFF                 # LOCK/STABLE/ENABLE status polls
        return None

    def write(self, uc, addr, size, value):
        # SIO GPIO output set/clr/xor (+ atomic aliases) — the LED lives here once
        # the app reaches loop().
        if SIO_BASE + 0x10 <= addr <= SIO_BASE + 0x28:
            self.gpio_writes += 1

    def code_hooks(self, symbols):
        hooks = []
        if "rom_func_lookup" in symbols:
            hooks.append(("rom_func_lookup", self._rom_lookup))
        for name in _MILESTONES:
            if name in symbols:
                hooks.append((name, self._make_reach(name)))
        return hooks

    def _rom_lookup(self, uc):
        # Emulate rom_func_lookup(code) -> pointer, by returning a staged no-op
        # thumb function (movs r0,#0 ; bx lr) so every bootrom call is a benign
        # success. Then return to the caller (keep the thumb bit in PC).
        uc.mem_write(ROM_STUB, b"\x00\x20\x70\x47")
        uc.reg_write(UC_ARM_REG_R0, ROM_STUB | 1)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def _make_reach(self, name):
        def hook(uc):
            if name not in self.reached:
                self.reached.append(name)
        return hook

    def done(self):
        return _STOP_AT in self.reached
