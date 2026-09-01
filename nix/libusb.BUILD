# @libusb — Nix-built libusb-1.0 (nixpkgs `libusb1`). pyOCD's pyusb backend
# dlopens this shared object at runtime instead of the prebuilt blob bundled in
# the libusb-package wheel; see //tools/pyocd for the injection shim.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# The real (non-symlink) shared library, per host OS: `libusb-1.0.so.0.x.y` on
# Linux, `libusb-1.0.x.dylib` on macOS. The version suffix tracks the nixpkgs
# pin. Both globs are declared (glob() runs at load time regardless of the
# select branch), so each is allow_empty on the other OS.
filegroup(
    name = "lib",
    srcs = select({
        "@platforms//os:macos": glob(["lib/libusb-1.0.*.dylib"], allow_empty = True),
        "//conditions:default": glob(["lib/libusb-1.0.so.0.*"], allow_empty = True),
    }),
)
