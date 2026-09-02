"""A minimal Cortex-M interrupt controller for the Unicorn full-app harness.

Unicorn emulates the ARM M-profile *core* (Thumb + the exception-return magic on
EXC_RETURN) but ships no NVIC/SCB machine model, so nothing ever *takes* an
exception: an interrupt-driven firmware (Embassy, RTIC, an RTOS) sits in its idle
`WFE`/`WFI` forever because the timer/peripheral IRQ that would wake it is never
delivered. This module supplies the missing piece — just enough NVIC + exception
entry/return to let peripheral models raise IRQs and have the firmware service
them.

Design
------
* We do exception *entry* by hand (stack the 8-word frame, set IPSR, vector the
  PC) and let a small sentinel drive *return*: LR is set to an unmapped-looking
  SENTINEL address whose execution we hook to pop the frame. This sidesteps
  depending on Unicorn's own EXC_RETURN handling (which varies by version) while
  staying fully re-entrant — the frame lives on the real MSP, so nesting works.
* Delivery is *cooperative*, evaluated at the firmware's idle `WFE`/`WFI` (the
  only place a well-behaved M-profile app waits for an interrupt) rather than on
  every instruction — cheap, and semantically right for an idle executor. The
  harness calls :meth:`deliver` there; peripheral models decide *when* to pend.
* Only what an ARMv6-M (Cortex-M0/M0+) app needs: MSP-only, no BASEPRI, no FP
  frame, PRIMASK masking, NVIC ISER/ICER/ISPR/ICPR + a modelled SysTick. ARMv7-M
  cores work too (they are a superset for this subset); extend as needed.
"""

from unicorn import UC_HOOK_CODE, UC_PROT_EXEC, UC_PROT_READ
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_PRIMASK,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_R12,
    UC_ARM_REG_SP,
    UC_ARM_REG_XPSR,
)

# Where the fabricated EXC_RETURN lands. Any mapped, otherwise-unused page works;
# execution reaching it means "an exception handler just returned". Kept well
# clear of the memory map and of real EXC_RETURN values (0xFFFFFFxx) — which the
# M-profile core reacts to — so a plain branch here just runs our return hook.
SENTINEL = 0x90000000
SENTINEL_SIZE = 0x1000

# SCS blocks we model (the harness maps the SCS as backing memory; we hook these).
SYST_CSR = 0xE000E010
SYST_RVR = 0xE000E014
SYST_CVR = 0xE000E018
NVIC_ISER = 0xE000E100
NVIC_ICER = 0xE000E180
NVIC_ISPR = 0xE000E200
NVIC_ICPR = 0xE000E280
SCB_VTOR = 0xE000ED08

# Exception numbers (== vector table index). External IRQ n is exception 16 + n.
EXC_SYSTICK = 15


def _u32(x):
    return x & 0xFFFFFFFF


class CortexMNvic:
    """NVIC + exception entry/return over a live Unicorn engine.

    Peripheral models pend interrupts with :meth:`pend_irq` (external IRQ number)
    or :meth:`pend_exc` (raw exception number). The harness drives :meth:`deliver`
    at the firmware's idle points and :meth:`tick_systick` as virtual time
    advances. Exposed to peripheral ``attach``/``on_idle`` hooks as ``uc.nvic``.
    """

    def __init__(self, uc, vtor):
        self.uc = uc
        self.vtor = vtor
        self.enabled = set()   # exception numbers with NVIC enable set
        self.pending = set()   # exception numbers pended, awaiting delivery
        self.active = []       # stack of in-flight exception numbers (for tracing)
        # SysTick model
        self.syst_reload = 0
        self.syst_enable = False
        self.syst_tickint = False
        self._syst_acc = 0
        self.trace = False

    # -- SCS / NVIC register access (installed by the harness as MMIO hooks) ---
    def scs_read(self, addr, size):
        if addr == SYST_CSR:
            # COUNTFLAG (bit16) reads as 0 here; ENABLE/TICKINT reflect config.
            return (1 if self.syst_enable else 0) | (2 if self.syst_tickint else 0)
        if addr == SYST_RVR:
            return self.syst_reload
        if addr == SYST_CVR:
            return 0
        if addr == SCB_VTOR:
            return self.vtor
        if NVIC_ISER <= addr < NVIC_ISER + 0x20:
            word = (addr - NVIC_ISER) // 4
            return self._irq_bits(self.enabled, word)
        if NVIC_ISPR <= addr < NVIC_ISPR + 0x20:
            word = (addr - NVIC_ISPR) // 4
            return self._irq_bits(self.pending, word)
        return None  # let backing memory answer

    def scs_write(self, addr, size, value):
        value = _u32(value)
        if addr == SYST_CSR:
            self.syst_enable = bool(value & 1)
            self.syst_tickint = bool(value & 2)
        elif addr == SYST_RVR:
            self.syst_reload = value & 0x00FFFFFF
        elif addr == SCB_VTOR:
            self.vtor = value
        elif NVIC_ISER <= addr < NVIC_ISER + 0x20:
            self._set_irq_bits(self.enabled, (addr - NVIC_ISER) // 4, value, on=True)
        elif NVIC_ICER <= addr < NVIC_ICER + 0x20:
            self._set_irq_bits(self.enabled, (addr - NVIC_ICER) // 4, value, on=False)
        elif NVIC_ISPR <= addr < NVIC_ISPR + 0x20:
            self._set_irq_bits(self.pending, (addr - NVIC_ISPR) // 4, value, on=True)
        elif NVIC_ICPR <= addr < NVIC_ICPR + 0x20:
            self._set_irq_bits(self.pending, (addr - NVIC_ICPR) // 4, value, on=False)

    def _irq_bits(self, excset, word):
        bits = 0
        for exc in excset:
            irq = exc - 16
            if irq >= 0 and irq // 32 == word:
                bits |= 1 << (irq % 32)
        return bits

    def _set_irq_bits(self, excset, word, value, on):
        for b in range(32):
            if value & (1 << b):
                exc = 16 + word * 32 + b
                if on:
                    excset.add(exc)
                else:
                    excset.discard(exc)

    # -- pending -------------------------------------------------------------
    def pend_irq(self, irq):
        self.pending.add(16 + irq)

    def pend_exc(self, exc):
        self.pending.add(exc)

    def tick_systick(self, ticks):
        """Advance the SysTick counter by `ticks`; pend SysTick on wrap."""
        if not (self.syst_enable and self.syst_tickint and self.syst_reload):
            return
        self._syst_acc += ticks
        period = self.syst_reload + 1
        if self._syst_acc >= period:
            self._syst_acc %= period
            self.pend_exc(EXC_SYSTICK)

    # -- delivery ------------------------------------------------------------
    def _ready_exc(self):
        """Lowest-numbered pending exception that is enabled and unmasked, or
        None. (SysTick is always 'enabled' when armed; external IRQs need ISER.)"""
        if self.uc.reg_read(UC_ARM_REG_PRIMASK) & 1:
            return None
        candidates = [e for e in self.pending
                      if e == EXC_SYSTICK or e in self.enabled]
        return min(candidates) if candidates else None

    def deliver(self):
        """If an exception is ready, perform entry and return True; else False."""
        exc = self._ready_exc()
        if exc is None:
            return False
        self.pending.discard(exc)
        self._enter(exc)
        return True

    def _enter(self, exc):
        uc = self.uc
        handler = int.from_bytes(uc.mem_read(self.vtor + exc * 4, 4), "little")
        sp = uc.reg_read(UC_ARM_REG_SP)
        pc = uc.reg_read(UC_ARM_REG_PC)
        xpsr = uc.reg_read(UC_ARM_REG_XPSR)

        # ARMv6-M double-word-aligns the frame on entry; record the pad in the
        # stacked xPSR bit 9 so return can undo it.
        aligned = sp & ~0x7
        pad = sp - aligned
        frame_xpsr = (xpsr | (1 << 24)) | (0x200 if pad else 0)  # keep Thumb; note align
        frame = aligned - 32
        regs = [
            uc.reg_read(UC_ARM_REG_R0),
            uc.reg_read(UC_ARM_REG_R1),
            uc.reg_read(UC_ARM_REG_R2),
            uc.reg_read(UC_ARM_REG_R3),
            uc.reg_read(UC_ARM_REG_R12),
            uc.reg_read(UC_ARM_REG_LR),
            pc,          # return address = where we were about to execute
            frame_xpsr,
        ]
        blob = b"".join(_u32(r).to_bytes(4, "little") for r in regs)
        uc.mem_write(frame, blob)
        uc.reg_write(UC_ARM_REG_SP, frame)
        uc.reg_write(UC_ARM_REG_LR, SENTINEL | 1)
        uc.reg_write(UC_ARM_REG_XPSR, (xpsr & ~0x1FF) | exc)  # IPSR = exc (handler mode)
        uc.reg_write(UC_ARM_REG_PC, handler | 1)  # keep the Thumb bit set (M-profile)
        self.active.append(exc)
        if self.trace:
            print("    [nvic] enter exc=%d handler=0x%08x sp=0x%08x" % (exc, handler, frame))

    def _return(self):
        uc = self.uc
        sp = uc.reg_read(UC_ARM_REG_SP)
        words = [int.from_bytes(uc.mem_read(sp + i * 4, 4), "little") for i in range(8)]
        r0, r1, r2, r3, r12, lr, ret_pc, frame_xpsr = words
        uc.reg_write(UC_ARM_REG_R0, r0)
        uc.reg_write(UC_ARM_REG_R1, r1)
        uc.reg_write(UC_ARM_REG_R2, r2)
        uc.reg_write(UC_ARM_REG_R3, r3)
        uc.reg_write(UC_ARM_REG_R12, r12)
        uc.reg_write(UC_ARM_REG_LR, lr)
        new_sp = sp + 32 + (4 if frame_xpsr & 0x200 else 0)  # undo entry alignment pad
        uc.reg_write(UC_ARM_REG_SP, new_sp)
        uc.reg_write(UC_ARM_REG_XPSR, frame_xpsr & ~0x200)   # restores IPSR=0 (thread)
        uc.reg_write(UC_ARM_REG_PC, ret_pc | 1)  # resume in Thumb at the return address
        if self.active:
            self.active.pop()
        if self.trace:
            print("    [nvic] return -> 0x%08x sp=0x%08x" % (ret_pc & ~1, new_sp))

    # -- install -------------------------------------------------------------
    def install(self):
        """Map the EXC_RETURN sentinel page and hook it to drive exception return."""
        try:
            self.uc.mem_map(SENTINEL, SENTINEL_SIZE, UC_PROT_READ | UC_PROT_EXEC)
        except Exception:
            pass
        # A dummy thumb instruction at the sentinel so a fetch there is valid; the
        # hook fires first and rewrites PC before it would execute.
        self.uc.mem_write(SENTINEL, b"\x00\xbf")  # nop
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, d: self._return(),
                         begin=SENTINEL, end=SENTINEL + 1)
