# @hidapi — Nix-built hidapi (nixpkgs `hidapi`). pyOCD only uses hidapi off-Linux
# (its requirement is marked `platform_system != "Linux"`); materialized here so
# the wrapper is complete on every platform. See //tools/pyocd.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# The libusb-backed hidapi variant (real, non-symlink versioned .so).
filegroup(
    name = "lib",
    srcs = glob(["lib/libhidapi-libusb.so.0.*"], allow_empty = False),
)
