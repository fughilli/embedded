// C++ stand-in for the Rust blink_timing crate on boards whose CPU upstream
// rustc can't target (classic ESP32: Xtensa LX6 needs the esp-rs rustc fork).
// Same header, same C ABI, same value — selected in place of the Rust static
// library by //apps/blink's select() so blink still builds for esp32.
#include "rust/blink_timing/blink_timing.h"

extern "C" uint32_t blink_interval_ms(void) { return 250; }
