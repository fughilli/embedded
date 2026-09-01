# @libclang — nixpkgs llvmPackages.libclang.lib. The rust_bindgen_toolchain
# `libclang` attr requires a CcInfo target and uses the shared lib's dir as
# LIBCLANG_PATH, so expose it as a cc_import. The soname differs per host OS:
# `libclang.dylib` on macOS, `libclang.so` on Linux.
package(default_visibility = ["//visibility:public"])

filegroup(name = "all", srcs = glob(["**"], allow_empty = False))

cc_import(
    name = "libclang",
    shared_library = select({
        "@platforms//os:macos": "lib/libclang.dylib",
        "//conditions:default": "lib/libclang.so",
    }),
)
