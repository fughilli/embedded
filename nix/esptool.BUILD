# BUILD for the @esptool external repo (nixpkgs esptool). Used by the esp32c6
# elf -> bin genrule.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

filegroup(
    name = "bin",
    srcs = ["bin/esptool"],
)
