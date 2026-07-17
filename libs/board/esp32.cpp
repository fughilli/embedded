// Classic ESP32 / ESP32-WROOM board support. The esp32 variant's
// pins_arduino.h defines no LED_BUILTIN; GPIO 2 is the onboard LED on the
// common DevKitC / WROOM-32 devkits.
#include <Arduino.h>

#include "libs/board/board.h"

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

extern "C" void board_setup(void) {
  pinMode(LED_BUILTIN, OUTPUT);
}

extern "C" void board_set_led(bool on) {
  digitalWrite(LED_BUILTIN, on ? HIGH : LOW);
}
