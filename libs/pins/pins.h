// Strip / pin configuration shared by LED apps.
#pragma once

// Number of LEDs on the strip (board-independent).
#define NUM_LEDS 64

// LED_DATA_PIN is provided per-board via the //libs/pins:pins target's select()
// (see BUILD.bazel). It must be a compile-time constant for FastLED's template.
#ifndef LED_DATA_PIN
#error "LED_DATA_PIN not defined — depend on //libs/pins and build for a board"
#endif
