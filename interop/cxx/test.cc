// C++ side of the cxx bridge demo: call the Rust `rust_scale` via the generated
// header.
#include <cassert>

#include "interop/cxx/src/lib.rs.h"

int main() {
  assert(demo::rust_scale(7) == 21);
  return 0;
}
