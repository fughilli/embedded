//! Exercises the bindgen-generated FFI for the `c_math` C library.
use c_math_rs::{add, point_sum, Point};

#[test]
fn calls_generated_c_bindings() {
    // bindgen emits `unsafe extern "C"` items; call them through the FFI.
    assert_eq!(unsafe { add(2, 3) }, 5);
    let p = Point { x: 10, y: 20 };
    assert_eq!(unsafe { point_sum(p) }, 30);
}
