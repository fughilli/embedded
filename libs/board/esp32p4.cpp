// ESP32-P4 board support. The P4 dev boards have no LED_BUILTIN; board_set_led is
// a no-op unless the variant defines one.
#include <Arduino.h>

#include "libs/board/board.h"

extern "C" void board_setup(void) {
#ifdef LED_BUILTIN
  pinMode(LED_BUILTIN, OUTPUT);
#endif
}

extern "C" void board_set_led(bool on) {
#ifdef LED_BUILTIN
  digitalWrite(LED_BUILTIN, on ? HIGH : LOW);
#else
  (void)on;
#endif
}
