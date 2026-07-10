// RP2350 blink. The arduino-pico core provides main() -> setup()/loop().
// The LED control is board-selected (//libs/board) and the blink interval is
// computed in Rust (//rust/blink_timing) — exercising the full C/C++/Rust link.
#include <Arduino.h>

#include "libs/board/board.h"

// Provided by the Rust static library (C ABI).
extern "C" uint32_t blink_interval_ms(void);

void setup() {
  board_setup();
}

void loop() {
  board_set_led(true);
  delay(blink_interval_ms());
  board_set_led(false);
  delay(blink_interval_ms());
}
