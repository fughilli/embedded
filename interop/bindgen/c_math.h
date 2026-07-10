// A tiny C API to demonstrate bindgen (C header -> Rust FFI).
#pragma once
#include <stdint.h>

typedef struct {
  int32_t x;
  int32_t y;
} Point;

int32_t add(int32_t a, int32_t b);
int32_t point_sum(Point p);
