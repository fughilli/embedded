// RP2350 board support: drive LED_BUILTIN via the Arduino API (arduino-pico).
#include <Arduino.h>

#include "libs/board/board.h"

extern "C" void board_setup(void) {
  pinMode(LED_BUILTIN, OUTPUT);
}

extern "C" void board_set_led(bool on) {
  digitalWrite(LED_BUILTIN, on ? HIGH : LOW);
}
