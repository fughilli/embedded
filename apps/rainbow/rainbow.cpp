// FastLED rainbow chaser (hue roll) on a 64-LED strip. Board-agnostic: the
// Arduino core is select()'d (via //libs/board) and the data pin comes from the
// per-board //libs/pins target.
#include <FastLED.h>

#include "libs/pins/pins.h"

static CRGB leds[NUM_LEDS];

void setup() {
  FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(64);
}

void loop() {
  // A full rainbow spread across the strip that scrolls each frame (the "hue
  // roll" / rainbow chaser): fill_rainbow paints leds[i] with hue + i*deltaHue,
  // and advancing the base hue every frame animates it along the strip.
  static uint8_t base_hue = 0;
  fill_rainbow(leds, NUM_LEDS, base_hue, /*deltaHue=*/4);
  FastLED.show();
  base_hue++;
  delay(20);
}
