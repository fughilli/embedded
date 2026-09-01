/* Firmware snippets exercised by the Unicorn simulator PoC (//apps/sim_demo).
 * Each is a plain leaf/recursive function the harness can call in isolation. */
#ifndef APPS_SIM_DEMO_SNIPPET_H_
#define APPS_SIM_DEMO_SNIPPET_H_

/* Pure arithmetic — cheapest possible stimulus. */
int sim_add(int a, int b);

/* Naive recursive Fibonacci — stack depth (and instruction count) grow with n,
 * so it exercises the max_stack / max_cycles measurements. */
int sim_fib(int n);

/* Allocate n ints from the sim heap, fill 0..n-1, return their sum. Exercises
 * the bump allocator and therefore the max_dynamic (heap canary) measurement. */
int sim_alloc_sum(int n);

/* Hardware single-precision FP: x*x*3 + x*2 + 1. Emits vmul/vfma.f32, proving
 * Unicorn's Cortex-M33 FPU works through the whole build+harness pipeline.
 * softfp ABI: args/return travel as float bit patterns in core registers. */
float sim_fpoly(float x);

#endif  /* APPS_SIM_DEMO_SNIPPET_H_ */
