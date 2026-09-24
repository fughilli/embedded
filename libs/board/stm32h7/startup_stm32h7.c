/* Reset vector + system exception table for the STM32H7 (Arm Cortex-M7).
 *
 * Single-M7-side view of the STM32H757 (Cube Orange+ autopilot MCU). Hand-written
 * (no CubeH7/CMSIS dependency) so the bare-metal benchmark firmware is fully
 * hermetic under Bazel + @arm_gcc. For a benchmark we only need the 16-entry
 * ARMv7-M *system* vector table (initial SP, reset, the core exceptions) — the
 * full ~150-entry peripheral IRQ table is unnecessary and omitted; reserved slots
 * are padded with 0. Reset_Handler enables the FPU FIRST (the H7 is a hard-float
 * build — see //toolchains/cc/stm32h7 — so the very first VFP instruction the C
 * runtime touches would UsageFault with the FPU disabled), then initialises the C
 * runtime (.data copy, .bss zero, C++ ctors) and calls main().
 *
 * Symbols (_sidata, _sdata, _edata, _sbss, _ebss, _estack) come from the
 * generated stm32h7 linker script (see //libs/board/stm32h7:stm32h7.bzl).
 */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;

extern int main(void);

/* Static-constructor tables emitted by the linker script (.preinit_array /
 * .init_array). We walk them directly rather than call newlib's
 * __libc_init_array(), which pulls in _init/_fini from crti/crtn — objects that
 * -nostartfiles omits. */
typedef void (*init_fn)(void);
extern init_fn __preinit_array_start[], __preinit_array_end[];
extern init_fn __init_array_start[], __init_array_end[];

void Reset_Handler(void);
void Default_Handler(void);

/* SCB->CPACR (Coprocessor Access Control Register) at 0xE000ED88. Setting bits
 * 20..23 (CP10/CP11 = full access) enables the FPU. Hand-written register access
 * (no CMSIS core headers), matching the stm32g0 startup's bare-metal style. */
#define SCB_CPACR (*(volatile uint32_t *)0xE000ED88u)

/* Copy .data from Flash to SRAM, zero .bss, run static constructors, main(). */
void Reset_Handler(void) {
  /* Enable the FPU (CP10/CP11 full access) before any float code runs. */
  SCB_CPACR |= (0xFu << 20);
  __asm volatile("dsb");
  __asm volatile("isb");

  /* TODO(bench-fidelity): enable the M7 I-cache / D-cache (SCB CCR + cache
   * maintenance) here once the benchmark harness decides on a cache config.
   * Left OUT for now so the first microbenchmarks measure the deterministic
   * no-cache path; cache is a fidelity knob, not a correctness requirement. */

  uint32_t *src = &_sidata;
  for (uint32_t *dst = &_sdata; dst < &_edata;) {
    *dst++ = *src++;
  }
  for (uint32_t *dst = &_sbss; dst < &_ebss;) {
    *dst++ = 0;
  }
  for (init_fn *fn = __preinit_array_start; fn < __preinit_array_end; ++fn) {
    (*fn)();
  }
  for (init_fn *fn = __init_array_start; fn < __init_array_end; ++fn) {
    (*fn)();
  }
  main();
  for (;;) {
  }
}

/* Weak default for every exception: park the core so faults are catchable. */
void Default_Handler(void) {
  for (;;) {
  }
}

/* Core system exceptions (ARMv7-M). Each is a weak alias of Default_Handler;
 * define a strong symbol of the same name to hook it. */
#define ALIAS(name) __attribute__((weak, alias("Default_Handler"))) void name(void)

ALIAS(NMI_Handler);
ALIAS(HardFault_Handler);
ALIAS(MemManage_Handler);
ALIAS(BusFault_Handler);
ALIAS(UsageFault_Handler);
ALIAS(SVC_Handler);
ALIAS(DebugMon_Handler);
ALIAS(PendSV_Handler);
ALIAS(SysTick_Handler);

/* The 16-entry ARMv7-M system vector table: initial SP, reset vector, then the
 * core exceptions (with the architecturally-reserved slots padded to 0). Placed
 * at 0x08000000 by the .isr_vector section. Peripheral IRQs (vector 16+) are
 * intentionally omitted — the benchmark firmware masks/does not use them. */
__attribute__((section(".isr_vector"), used))
void (*const g_pfnVectors[])(void) = {
    (void (*)(void))(&_estack),  /* 0x00 initial stack pointer */
    Reset_Handler,               /* 0x04 reset */
    NMI_Handler,                 /* 0x08 */
    HardFault_Handler,           /* 0x0C */
    MemManage_Handler,           /* 0x10 */
    BusFault_Handler,            /* 0x14 */
    UsageFault_Handler,          /* 0x18 */
    0, 0, 0, 0,                  /* 0x1C..0x28 reserved */
    SVC_Handler,                 /* 0x2C */
    DebugMon_Handler,            /* 0x30 */
    0,                           /* 0x34 reserved */
    PendSV_Handler,              /* 0x38 */
    SysTick_Handler,             /* 0x3C */
};
