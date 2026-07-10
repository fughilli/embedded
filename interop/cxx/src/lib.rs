//! cxx bridge demo: expose a Rust function to C++ with the `cxx` crate.
//! Host-targeted — cxx uses `std`, so it is not for `no_std` firmware (bindgen
//! + cbindgen cover the embedded C-ABI interop).

#[cxx::bridge(namespace = "demo")]
mod ffi {
    extern "Rust" {
        fn rust_scale(x: u32) -> u32;
    }
}

fn rust_scale(x: u32) -> u32 {
    x * 3
}
