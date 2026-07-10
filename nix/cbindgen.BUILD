# BUILD for the @cbindgen external repo (nixpkgs rust-cbindgen). Used by
# //rules:cbindgen.bzl to generate C/C++ headers from Rust.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

filegroup(
    name = "bin",
    srcs = ["bin/cbindgen"],
)
