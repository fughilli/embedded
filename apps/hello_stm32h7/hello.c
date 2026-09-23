/* Minimal bring-up firmware for the STM32H757 (Cortex-M7) benchmark foundation:
 * enable the FPU (in Reset_Handler, see //libs/board/stm32h7), print over ARM
 * semihosting, and spin. Validates the H7 toolchain + startup + linker script +
 * semihosting library all link and run. The DWT-timed microbenchmark firmware
 * builds on this scaffold. */
#include "libs/semihost/semihost.h"

int main(void) {
  semihost_puts("hello from CM7\n");
  for (;;) {
  }
}
