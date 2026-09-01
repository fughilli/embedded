#include "apps/sim_demo/snippet.h"

#include <stdlib.h>  /* malloc — provided by //rules/sim:sim_rt in the stub */

int sim_add(int a, int b) { return a + b; }

int sim_fib(int n) {
  if (n < 2) {
    return n;
  }
  return sim_fib(n - 1) + sim_fib(n - 2);
}

int sim_alloc_sum(int n) {
  int *xs = (int *)malloc((size_t)n * sizeof(int));
  if (!xs) {
    return -1;
  }
  int sum = 0;
  for (int i = 0; i < n; i++) {
    xs[i] = i;
    sum += xs[i];
  }
  return sum;
}

float sim_fpoly(float x) { return x * x * 3.0f + x * 2.0f + 1.0f; }
