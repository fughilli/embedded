# @libusb — Nix-built libusb-1.0 (nixpkgs `libusb1`). pyOCD's pyusb backend
# dlopens this shared object at runtime instead of the prebuilt blob bundled in
# the libusb-package wheel; see //tools/pyocd for the injection shim.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# The real (non-symlink) versioned .so; the suffix tracks the nixpkgs pin.
filegroup(
    name = "lib",
    srcs = glob(["lib/libusb-1.0.so.0.*"], allow_empty = False),
)
