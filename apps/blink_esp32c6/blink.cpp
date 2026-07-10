// ESP32-C6 blink. The arduino-esp32 core provides app_main()/main() ->
// setup()/loop(). LED control is board-selected (//libs/board) and the blink
// interval is computed in Rust (//rust/blink_timing) — same C/C++/Rust link as
// the RP2350 app, retargeted to the RISC-V core by the embedded_binary transition.
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
