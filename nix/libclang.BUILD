# @libclang — nixpkgs llvmPackages.libclang.lib. The rust_bindgen_toolchain
# `libclang` attr requires a CcInfo target and uses the .so's dir as
# LIBCLANG_PATH, so expose it as a cc_import.
package(default_visibility = ["//visibility:public"])

filegroup(name = "all", srcs = glob(["**"], allow_empty = False))

cc_import(
    name = "libclang",
    shared_library = "lib/libclang.so",
)
