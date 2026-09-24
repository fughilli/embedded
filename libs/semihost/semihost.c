/* ARM semihosting implementation. See semihost.h. */
#include "libs/semihost/semihost.h"

/* CoreDebug->DHCSR (Debug Halting Control and Status Register), 0xE000EDF0.
 * Bit 0 (C_DEBUGEN) is set by an attached debugger that has enabled halting
 * debug. When clear, a semihosting bkpt would HardFault, so we short-circuit. */
#define CORE_DEBUG_DHCSR (*(volatile uint32_t *)0xE000EDF0u)
#define DHCSR_C_DEBUGEN (1u << 0)

/* ADP_Stopped_ApplicationExit: the standard reason code SYS_EXIT reports for a
 * normal application exit. The exit code is passed as a subcode (see below). */
#define ADP_STOPPED_APPLICATION_EXIT 0x20026u

int semihost_debugger_present(void) {
  return (CORE_DEBUG_DHCSR & DHCSR_C_DEBUGEN) != 0u;
}

int32_t semihost_call(int op, void *arg) {
  if (!semihost_debugger_present()) {
    return -1;
  }
  register int r0 __asm__("r0") = op;
  register void *r1 __asm__("r1") = arg;
  __asm__ volatile("bkpt 0xAB"
                   : "+r"(r0)
                   : "r"(r1)
                   : "memory");
  return (int32_t)r0;
}

void semihost_putc(char c) {
  /* SYS_WRITEC: r1 points at the single character to emit. */
  semihost_call(SEMIHOST_SYS_WRITEC, &c);
}

void semihost_puts(const char *s) {
  /* SYS_WRITE0: r1 points at a NUL-terminated string. Cast away const — the
   * semihosting op only reads it. */
  semihost_call(SEMIHOST_SYS_WRITE0, (void *)s);
}

void semihost_write_hex(uint32_t v) {
  static const char kHex[] = "0123456789abcdef";
  char buf[11];
  buf[0] = '0';
  buf[1] = 'x';
  for (int i = 0; i < 8; ++i) {
    buf[2 + i] = kHex[(v >> ((7 - i) * 4)) & 0xFu];
  }
  buf[10] = '\0';
  semihost_puts(buf);
}

void semihost_exit(int code) {
  /* SYS_EXIT. On 32-bit targets the ARM spec passes a two-word block
   * {reason, subcode}; subcode carries the application exit status. Older/QEMU
   * hosts accept the bare reason in r1, but the block form is the portable one. */
  uint32_t block[2] = {ADP_STOPPED_APPLICATION_EXIT, (uint32_t)code};
  semihost_call(SEMIHOST_SYS_EXIT, block);
}
