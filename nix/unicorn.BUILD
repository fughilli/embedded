# @unicorn — Nix-built libunicorn (nixpkgs `unicorn`, the CPU emulator C library).
# The pip `unicorn` Python bindings (ctypes) dlopen this shared object at runtime
# instead of the prebuilt blob bundled in the manylinux wheel; the sim harness
# points them here via LIBUNICORN_PATH (see //rules/sim:unicorn_nix). This is the
# "native component of the unicorn python package supplied by Nix" the sim stack
# is built on.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# The real (non-symlink) shared library, per host OS: `libunicorn.so.2` on Linux,
# `libunicorn.2.dylib` on macOS — exactly the sonames the unicorn Python loader
# probes for under LIBUNICORN_PATH. Both globs are declared (glob runs at load
# time regardless of the select branch), so each is allow_empty on the other OS.
filegroup(
    name = "lib",
    srcs = select({
        "@platforms//os:macos": glob(["lib/libunicorn.*.dylib"], allow_empty = True),
        "//conditions:default": glob(["lib/libunicorn.so.*"], allow_empty = True),
    }),
)
