# BUILD for the @picotool external repo (Nix-provided picotool 2.2.x).
# Used by the elf -> uf2 genrule in apps/blink_rp2350.
package(default_visibility = ["//visibility:public"])

filegroup(
    name = "all",
    srcs = glob(["**"], allow_empty = False),
)

# The executable, referenced with $(execpath @picotool//:bin) from genrules.
filegroup(
    name = "bin",
    srcs = ["bin/picotool"],
)
