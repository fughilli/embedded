// ESP32-C6 board support (Milestone 2). Stub for now — dependency-free so the
// select() branch analyzes on any host; fill in with the arduino-esp32 core
// once the C6 toolchain lands.
#include "libs/board/board.h"

extern "C" void board_setup(void) {
  // TODO(milestone-2): pinMode(LED_BUILTIN, OUTPUT) via arduino-esp32.
}

extern "C" void board_set_led(bool on) {
  (void)on;
  // TODO(milestone-2): digitalWrite(LED_BUILTIN, on).
}
