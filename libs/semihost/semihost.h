/* ARM semihosting over `bkpt 0xAB` — host-side console I/O + exit for bare-metal
 * Cortex-M firmware being run under a debugger (pyOCD/OpenOCD/QEMU). Pure
 * Cortex-M, no board dependency: usable by any ARMv6-M/v7-M/v8-M target.
 *
 * IMPORTANT: a semihosting `bkpt 0xAB` with NO debugger attached takes a HardFault
 * (nothing services the breakpoint). Every entry point here first checks whether a
 * debugger is present (CoreDebug->DHCSR C_DEBUGEN) and becomes a silent no-op if
 * not — so linking this into a benchmark that may also run standalone is safe.
 */
#ifndef LIBS_SEMIHOST_SEMIHOST_H_
#define LIBS_SEMIHOST_SEMIHOST_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Semihosting operation numbers (r0), ARM semihosting spec. */
#define SEMIHOST_SYS_WRITEC 0x03 /* r1 -> ptr to one char */
#define SEMIHOST_SYS_WRITE0 0x04 /* r1 -> NUL-terminated string */
#define SEMIHOST_SYS_WRITE 0x05  /* r1 -> {handle, ptr, len} block */
#define SEMIHOST_SYS_EXIT 0x18   /* r1 -> reason code / {code,subcode} */

/* Raw semihosting call: op in r0, arg in r1, `bkpt 0xAB`; returns r0. No-op
 * (returns -1) when no debugger is attached. */
int32_t semihost_call(int op, void *arg);

/* True iff a debugger has enabled halting debug (CoreDebug->DHCSR C_DEBUGEN). */
int semihost_debugger_present(void);

/* Console helpers (all no-ops without a debugger). */
void semihost_putc(char c);
void semihost_puts(const char *s);         /* SYS_WRITE0 (NUL-terminated) */
void semihost_write_hex(uint32_t v);       /* "0x" + 8 hex digits */

/* Ask the host debugger to terminate the session with `code`. */
void semihost_exit(int code);

#ifdef __cplusplus
}
#endif

#endif  /* LIBS_SEMIHOST_SEMIHOST_H_ */
