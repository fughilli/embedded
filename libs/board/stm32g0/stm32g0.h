// STM32G0 bare-metal board support. Implements the shared //libs/board:board.h
// interface (board_setup / board_set_led) with direct register access, plus a
// coarse busy-wait delay for the demo app (no Arduino core / SysTick on this
// board). The G0 register map is identical family-wide, so this serves any G0.
#pragma once

#include "libs/board/board.h"

#ifdef __cplusplus
extern "C" {
#endif

// Approximate busy-wait. The core boots on the 16 MHz HSI, so this is a rough
// software delay (not timer-accurate) — enough to make the LED blink visible.
void board_delay_ms(unsigned ms);

#ifdef __cplusplus
}
#endif
