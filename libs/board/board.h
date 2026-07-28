// Minimal board-support interface. The implementation is chosen per-platform by
// a select() in the BUILD file (see //libs/board:BUILD.bazel) — this is the
// platform-support code the embedded_binary transition switches between.
#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Configure the on-board LED for output.
void board_setup(void);

// Drive the on-board LED.
void board_set_led(bool on);

#ifdef __cplusplus
}
#endif
