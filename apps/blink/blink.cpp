// Shared blink firmware for both boards. The Arduino core provides the entry
// point (main/app_main) which calls setup()/loop(). The board-specific core and
// LED control are chosen by select() (see BUILD.bazel and //libs/board); the
// blink interval is computed in Rust (//rust/blink_timing).
#include <Arduino.h>

#include "libs/board/board.h"
// cbindgen-generated from //rust/blink_timing (Rust -> C header).
#include "rust/blink_timing/blink_timing.h"

void setup() {
  board_setup();
}

void loop() {
  board_set_led(true);
  delay(blink_interval_ms());
  board_set_led(false);
  delay(blink_interval_ms());
}
