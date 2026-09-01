// Bare-metal blink for the STM32G0B1 (Arm Cortex-M0+). No Arduino core: the
// entry point is main(), called by Reset_Handler in //libs/board/stm32g0 after
// it sets up the C runtime. Toggles the on-board LED (PA5 / LD4) forever.
#include "libs/board/stm32g0/stm32g0.h"

int main(void) {
  board_setup();
  for (;;) {
    board_set_led(true);
    board_delay_ms(500);
    board_set_led(false);
    board_delay_ms(500);
  }
}
