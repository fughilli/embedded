/* Sim runtime: the tiny freestanding support linked into every simulation stub.
 *
 * The Unicorn harness loads the stub by VMA (so .data is already initialized and
 * .bss already zero before any stimulus runs) and calls firmware functions
 * directly — it does not run the reset path. This runtime therefore only has to
 * provide a heap the harness can account for: `malloc`/`free` bump-allocate from
 * the linker's `.sim_heap` region (_sim_heap_start.._sim_heap_end), so heap use
 * shows up as canary bytes the harness scans for max_dynamic. A minimal `_start`
 * is provided as the ELF entry for completeness. */
#ifndef RULES_SIM_RT_SIM_RT_H_
#define RULES_SIM_RT_SIM_RT_H_

#include <stddef.h>

void *malloc(size_t n);
void free(void *p);
void _start(void);

#endif  /* RULES_SIM_RT_SIM_RT_H_ */
