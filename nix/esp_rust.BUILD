# BUILD for the @esp_rust external repo (esp-rs rustc fork + the prebuilt
# xtensa-esp32-none-elf sysroot from nix/esp_rust.nix). Wired into a
# rust_toolchain by //toolchains/rust/esp32 (which wraps the sysroot rlibs in
# rust_stdlib_filegroup: this generated repo can't see @rules_rust).

package(default_visibility = ["//visibility:public"])

filegroup(
    name = "rustc",
    srcs = ["bin/rustc"],
)

filegroup(
    name = "rustdoc",
    srcs = ["bin/rustdoc"],
)

# rustc's own shared libraries (librustc_driver, its LLVM) — must sit next to
# the binary in the sandbox.
filegroup(
    name = "rustc_lib",
    srcs = glob(
        [
            "lib/*.so",
            "lib/*.so.*",
            "lib/*.dylib",
        ],
        allow_empty = True,
    ),
)

filegroup(
    name = "sysroot_xtensa_esp32",
    srcs = glob(["lib/rustlib/xtensa-esp32-none-elf/lib/*.rlib"]),
)
