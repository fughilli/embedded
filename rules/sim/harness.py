"""The Unicorn execution harness. Two modes, one memory/ELF-loading core:

Stub perf-test mode (:class:`Simulator`) — given a stub ELF + platform emu config,
maps memory, loads PT_LOAD by VMA (so .data/.bss are ready without running reset),
and for each :class:`~stimulus.Stimulus` sets up the ARM calling convention, runs
until return, counts retired instructions (+ virtual cycles if a timing model is
present), and measures peak stack/heap via canaries + static footprint.

Full-app mode (:func:`boot_app`) — boots the *exact* firmware ELF from its reset
vector (SP/PC from the vector table) and runs it unmodified, with :mod:`peripherals`
device models servicing MMIO. A model's ``done()`` stops emulation once the app has
shown enough behavior to judge (firmware main loops never return).

ARMv8-M (Cortex-M33) and ARMv6-M (Cortex-M0/M0+) are wired up; add to _ARCH_CPU.
"""

import unicorn_nix

unicorn_nix.install()  # point LIBUNICORN_PATH at the Nix libunicorn before import

import unicorn.arm_const as _arm  # noqa: E402
from unicorn import (  # noqa: E402
    UC_ARCH_ARM,
    UC_HOOK_CODE,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MODE_MCLASS,
    UC_MODE_THUMB,
    UC_PROT_EXEC,
    UC_PROT_READ,
    UC_PROT_WRITE,
    Uc,
    UcError,
)
from unicorn.arm_const import (  # noqa: E402
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_SP,
)

from elftools.elf.elffile import ELFFile  # noqa: E402

from stimulus import Buffer  # noqa: E402

_ARG_REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]

# Distinct 4-byte canaries so a legitimate write of one region's fill value can't
# masquerade as "untouched" in another; the low bytes vary per word (see _paint).
_STACK_CANARY = 0xCAFE0000
_HEAP_CANARY = 0xF00D0000

# architecture -> Unicorn CPU model. All are ARM M-profile (thumb + mclass); the
# model selects the exact ISA (FP, DSP, ...). Names are looked up on arm_const so
# a missing model on an older unicorn degrades gracefully to the default core.
_ARCH_CPU = {
    "armv8-m": "UC_CPU_ARM_CORTEX_M33",
    "armv6-m": "UC_CPU_ARM_CORTEX_M0",
}


class SimError(Exception):
    pass


def _new_uc(arch):
    if arch not in _ARCH_CPU:
        raise SimError("unsupported architecture %r (known: %s)" %
                       (arch, ", ".join(sorted(_ARCH_CPU))))
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    model = getattr(_arm, _ARCH_CPU[arch], None)
    if model is not None:
        try:
            uc.ctl_set_cpu_model(model)
        except Exception:
            pass  # older unicorn: default core still decodes the M-profile ISA
    return uc


def _load_pt_load(uc, elf):
    """Write every PT_LOAD segment by VMA (.bss tail zero-filled). Returns the
    (vaddr, image) list so callers can restore initial state later."""
    segments = []
    for seg in elf.iter_segments():
        if seg["p_type"] != "PT_LOAD":
            continue
        vaddr = seg["p_vaddr"]
        data = seg.data()
        pad = seg["p_memsz"] - len(data)
        image = data + (b"\x00" * pad if pad > 0 else b"")
        uc.mem_write(vaddr, image)
        segments.append((vaddr, image))
    return segments


def _enable_fpu_uc(uc):
    """Grant full FP access via CPACR, as a firmware reset/SystemInit would
    (CP10/CP11 = 0b11). Best-effort; a no-op on cores without an FPU."""
    SCS, CPACR = 0xE000E000, 0xE000ED88
    try:
        uc.mem_map(SCS, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
    except UcError:
        pass
    try:
        uc.mem_write(CPACR, (0x00F00000).to_bytes(4, "little"))
    except UcError:
        pass


class StimulusResult:
    def __init__(self, stim, index, ret, instructions, cycles, output):
        self.stim = stim
        self.index = index
        self.ret = ret
        self.instructions = instructions
        self.cycles = cycles
        self.output = output  # bytes read back from the first out Buffer, or None

    @property
    def passed(self):
        return (self.stim.expected_return is None or
                self.ret == (self.stim.expected_return & 0xFFFFFFFF))


class SimReport:
    def __init__(self):
        self.results = []
        self.peak_instructions = 0
        self.peak_cycles = 0
        self.peak_stack = 0
        self.peak_dynamic = 0
        self.static_bytes = 0


def _paint(uc, base, size, seed):
    """Fill [base, base+size) with per-word canaries (word i = seed | i)."""
    words = size // 4
    buf = bytearray(size)
    for i in range(words):
        buf[i * 4:(i + 1) * 4] = ((seed | (i & 0xFFFF)) & 0xFFFFFFFF).to_bytes(4, "little")
    uc.mem_write(base, bytes(buf))


def _scan_touched_from_top(uc, low, high, seed):
    """Stack grows down from `high`. Return bytes touched = high - lowest word
    that no longer holds its canary."""
    data = uc.mem_read(low, high - low)
    words = (high - low) // 4
    for i in range(words):  # walk from the low end upward
        expected = ((seed | (i & 0xFFFF)) & 0xFFFFFFFF).to_bytes(4, "little")
        if data[i * 4:(i + 1) * 4] != expected:
            return high - (low + i * 4)
    return 0


def _scan_touched_from_bottom(uc, low, high, seed):
    """Heap grows up from `low`. Return bytes touched = (highest touched word
    end) - low."""
    data = uc.mem_read(low, high - low)
    words = (high - low) // 4
    for i in range(words - 1, -1, -1):  # walk from the high end downward
        expected = ((seed | (i & 0xFFFF)) & 0xFFFFFFFF).to_bytes(4, "little")
        if data[i * 4:(i + 1) * 4] != expected:
            return (i + 1) * 4
    return 0


def _uc_prot(perm):
    p = 0
    if "r" in perm:
        p |= UC_PROT_READ
    if "w" in perm:
        p |= UC_PROT_WRITE
    if "x" in perm:
        p |= UC_PROT_EXEC
    return p


def _align_region(base, size):
    """Unicorn requires page (4K) aligned map base/size."""
    page = 0x1000
    lo = base & ~(page - 1)
    hi = (base + size + page - 1) & ~(page - 1)
    return lo, hi - lo


class Simulator:
    def __init__(self, elf_path, emu_config):
        self.emu = emu_config
        self.uc = _new_uc(emu_config["architecture"])
        self.symbols = {}
        self._static_bytes = 0
        self._map_regions()
        self._map_sentinel()
        self._enable_fpu()
        self._load_elf(elf_path)
        self._read_layout_symbols()

    # -- setup -------------------------------------------------------------
    def _map_regions(self):
        for r in self.emu["regions"]:
            base, size = _align_region(r["base"], r["size"])
            self.uc.mem_map(base, size, _uc_prot(r["perm"]))

    def _map_sentinel(self):
        s = self.emu["sentinel"]
        self.sentinel = s["base"]
        self.uc.mem_map(s["base"], s["size"], UC_PROT_READ | UC_PROT_EXEC)

    def _enable_fpu(self):
        # When calling functions directly the harness skips reset, so it enables
        # FP itself (as SystemInit would). See _enable_fpu_uc.
        _enable_fpu_uc(self.uc)

    def _load_elf(self, elf_path):
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)
            # Capture PT_LOAD segments so memory can be restored to its initial
            # (post-reset) state before every stimulus — otherwise mutable globals
            # (e.g. the heap bump pointer) leak between stimuli and per-stimulus
            # peaks (max_dynamic!) become cumulative.
            self._segments = _load_pt_load(self.uc, elf)

            symtab = elf.get_section_by_name(".symtab")
            if symtab is not None:
                for sym in symtab.iter_symbols():
                    if sym.entry["st_value"]:
                        self.symbols[sym.name] = sym.entry["st_value"]
            # static footprint = .data + .bss
            for name in (".data", ".bss"):
                sec = elf.get_section_by_name(name)
                if sec is not None:
                    self._static_bytes += sec["sh_size"]

    def _read_layout_symbols(self):
        need = ("_estack", "_sim_stack_limit", "_sim_heap_start", "_sim_heap_end")
        missing = [s for s in need if s not in self.symbols]
        if missing:
            raise SimError("stub ELF is missing linker symbols %r — is it linked "
                           "with the generated sim linker script?" % missing)
        self.stack_top = self.symbols["_estack"]
        self.stack_limit = self.symbols["_sim_stack_limit"]
        self.heap_start = self.symbols["_sim_heap_start"]
        self.heap_end = self.symbols["_sim_heap_end"]

    def _reset_memory(self):
        for vaddr, image in self._segments:
            self.uc.mem_write(vaddr, image)

    # -- execution ---------------------------------------------------------
    def _resolve(self, entrypoint):
        # accept a symbol name or a raw integer address
        if isinstance(entrypoint, int):
            return entrypoint
        if entrypoint in self.symbols:
            return self.symbols[entrypoint]
        if ("%s" % entrypoint) in self.symbols:
            return self.symbols[entrypoint]
        raise SimError("no symbol %r in stub ELF (have e.g. %s)" %
                       (entrypoint, ", ".join(list(self.symbols)[:8])))

    def _cycle_cost(self, count):
        tm = self.emu.get("timing_model")
        if not tm:
            return count
        return count * tm.get("cycles_per_instruction", 1)

    def run_stimulus(self, stim, index):
        uc = self.uc
        # Restore .data/.bss (resets globals like the heap bump pointer), then
        # repaint canaries so each stimulus measures its own peak usage.
        self._reset_memory()
        _paint(uc, self.stack_limit, self.stack_top - self.stack_limit, _STACK_CANARY)
        _paint(uc, self.heap_start, self.heap_end - self.heap_start, _HEAP_CANARY)

        # Stage pointer arguments in the heap, scalars go straight to registers.
        reg_vals = []
        staged = []  # (addr, out_len) for read-back
        bump = self.heap_start
        for a in stim.args:
            if isinstance(a, Buffer):
                addr = (bump + 7) & ~7
                uc.mem_write(addr, a.data)
                bump = addr + max(len(a.data), a.out_len)
                reg_vals.append(addr)
                staged.append((addr, a.out_len))
            else:
                reg_vals.append(a & 0xFFFFFFFF)
        if len(reg_vals) > len(_ARG_REGS):
            raise SimError("stimulus %s: >%d args not supported (no stack args yet)"
                           % (stim.label(index), len(_ARG_REGS)))
        for reg, val in zip(_ARG_REGS, reg_vals):
            uc.reg_write(reg, val)

        uc.reg_write(UC_ARM_REG_SP, self.stack_top)
        uc.reg_write(UC_ARM_REG_LR, self.sentinel | 1)  # thumb bit

        counter = {"n": 0}

        def _count(uc_, addr, size, _ud):
            counter["n"] += 1

        h = uc.hook_add(UC_HOOK_CODE, _count)
        addr = self._resolve(stim.entrypoint)
        try:
            uc.emu_start(addr | 1, self.sentinel, timeout=0, count=0)
        except UcError as e:
            raise SimError("stimulus %s faulted: %s (pc=0x%x)" %
                           (stim.label(index), e, uc.reg_read(UC_ARM_REG_PC)))
        finally:
            uc.hook_del(h)

        ret = uc.reg_read(UC_ARM_REG_R0)
        instructions = counter["n"]
        cycles = self._cycle_cost(instructions)
        output = None
        if staged and staged[0][1]:
            addr, out_len = staged[0]
            output = bytes(uc.mem_read(addr, out_len))
        return StimulusResult(stim, index, ret, instructions, cycles, output)

    def stack_used(self):
        return _scan_touched_from_top(self.uc, self.stack_limit, self.stack_top, _STACK_CANARY)

    def dynamic_used(self):
        return _scan_touched_from_bottom(self.uc, self.heap_start, self.heap_end, _HEAP_CANARY)

    @property
    def static_bytes(self):
        return self._static_bytes


def run(elf_path, emu_config, stimuli):
    """Run all stimuli and return a :class:`SimReport`. Per-stimulus stack/heap
    peaks are captured immediately after each run."""
    sim = Simulator(elf_path, emu_config)
    report = SimReport()
    report.static_bytes = sim.static_bytes
    for i, stim in enumerate(stimuli):
        res = sim.run_stimulus(stim, i)
        report.results.append(res)
        report.peak_instructions = max(report.peak_instructions, res.instructions)
        report.peak_cycles = max(report.peak_cycles, res.cycles)
        report.peak_stack = max(report.peak_stack, sim.stack_used())
        report.peak_dynamic = max(report.peak_dynamic, sim.dynamic_used())
    return report


# ---------------------------------------------------------------------------
# Full-app mode: boot the exact firmware ELF from reset with virtual peripherals.
# ---------------------------------------------------------------------------
class AppResult:
    def __init__(self, uc, peripherals, instructions, hit_budget):
        self.uc = uc
        self.peripherals = peripherals
        self.instructions = instructions
        self.hit_budget = hit_budget  # True if the cycle budget stopped it

    def by_name(self, sim_name):
        """The instantiated peripheral registered under `sim_name`, or None."""
        for p in self.peripherals:
            if getattr(type(p), "sim_name", None) == sim_name:
                return p
        return None


def _install_peripheral(uc, p):
    """Route reads/writes in the peripheral's MMIO ranges into the model. Backing
    memory (mapped as RAM) answers plain reads/holds written values; the hooks add
    register side effects + let the model stop the run via done()."""
    def on_write(uc_, access, addr, size, value, _ud):
        p.write(uc_, addr, size, value)
        if p.done():
            uc_.emu_stop()

    def on_read(uc_, access, addr, size, value, _ud):
        v = p.read(uc_, addr, size)
        if v is not None:
            uc_.mem_write(addr, int(v).to_bytes(size, "little"))

    for base, size in p.regions():
        uc.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=base, end=base + size)
        uc.hook_add(UC_HOOK_MEM_READ, on_read, begin=base, end=base + size)


def boot_app(elf_path, emu_config, peripherals=(), max_cycles=None, count_instructions=False):
    """Boot the firmware ELF from its reset vector and run it with `peripherals`.

    Stops when a peripheral's done() fires or the `max_cycles` instruction budget
    is hit (firmware main loops never return). `count_instructions` adds a per-
    instruction hook (needed for a retired-instruction count, but ~20x slower —
    off by default so busy-wait delays run at native speed)."""
    if emu_config.get("boot") != "reset":
        raise SimError("boot_app requires the platform's boot mode to be 'reset'")
    uc = _new_uc(emu_config["architecture"])

    for r in emu_config["regions"]:
        base, size = _align_region(r["base"], r["size"])
        uc.mem_map(base, size, _uc_prot(r["perm"]))
    _enable_fpu_uc(uc)

    with open(elf_path, "rb") as f:
        _load_pt_load(uc, ELFFile(f))

    for p in peripherals:
        _install_peripheral(uc, p)

    vt = emu_config["vector_table"]
    sp = int.from_bytes(uc.mem_read(vt, 4), "little")
    pc = int.from_bytes(uc.mem_read(vt + 4, 4), "little")
    uc.reg_write(UC_ARM_REG_SP, sp)

    counter = {"n": 0}
    if count_instructions:
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: counter.__setitem__("n", counter["n"] + 1))

    budget = max_cycles or 100_000_000  # hard cap so a non-blinking app can't hang
    try:
        uc.emu_start(pc, 0, timeout=0, count=budget)
    except UcError as e:
        raise SimError("app faulted: %s (pc=0x%x)" % (e, uc.reg_read(UC_ARM_REG_PC)))

    done = any(p.done() for p in peripherals)
    return AppResult(uc, list(peripherals), counter["n"], hit_budget=not done)
