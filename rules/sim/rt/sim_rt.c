/* Sim runtime — see sim_rt.h. Freestanding; no OS, no syscalls. */
#include "rules/sim/rt/sim_rt.h"

#include <stdint.h>

/* Linker-provided bounds (see the generated sim linker script). */
extern uint8_t _sim_heap_start[];
extern uint8_t _sim_heap_end[];

/* Bump pointer. Lives in .bss, so the harness's VMA load zeroes it; malloc
 * lazy-inits it to _sim_heap_start on first use (no reset code required). */
static uint8_t *g_brk;

void *malloc(size_t n) {
  if (g_brk == 0) {
    g_brk = _sim_heap_start;
  }
  /* 8-byte align so returned pointers suit any scalar. */
  uintptr_t a = (uintptr_t)g_brk;
  a = (a + 7u) & ~(uintptr_t)7u;
  uint8_t *p = (uint8_t *)a;
  if (p + n > _sim_heap_end) {
    return 0; /* out of heap */
  }
  g_brk = p + n;
  return p;
}

/* Bump allocator: individual frees are no-ops. (max_dynamic measures peak
 * high-water mark, which is exactly what a firmware arena cares about.) */
void free(void *p) { (void)p; }

/* Linker-provided section bounds for a real reset (harness never calls this). */
extern uint8_t __data_start__[], __data_end__[], _sidata[];
extern uint8_t __bss_start__[], __bss_end__[];

/* ELF entry point. On real silicon this would run before main(); under the
 * emulator the harness loads by VMA and calls functions directly, so this is
 * only here to give the ELF a valid ENTRY and to document the reset contract. */
void _start(void) {
  uint8_t *src = _sidata;
  for (uint8_t *d = __data_start__; d < __data_end__;) {
    *d++ = *src++;
  }
  for (uint8_t *b = __bss_start__; b < __bss_end__;) {
    *b++ = 0;
  }
  for (;;) {
  }
}
