//! no_std Rust module linked into the firmware to prove the C↔Rust path.
//! The C++ blink loop calls `blink_interval_ms()` to get its delay.
#![no_std]

use core::panic::PanicInfo;

/// Blink half-period in milliseconds. Computed in Rust, consumed from C++ via
/// the C ABI (`extern "C"` + no name mangling).
#[no_mangle]
pub extern "C" fn blink_interval_ms() -> u32 {
    250
}

/// no_std requires a panic handler. Firmware has nowhere to unwind to, so spin.
/// (We also build with -Cpanic=abort — see BUILD.bazel — to avoid needing the
/// eh_personality lang item.)
#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}
