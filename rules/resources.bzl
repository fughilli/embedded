"""`c_resource_library`: embed resource files (HTML, images, ...) as C const
char arrays via codegen, so firmware sources don't inline big string literals.

    load("//rules:resources.bzl", "c_resource_library")
    c_resource_library(name = "page", srcs = ["page.html"])

yields a cc_library exposing `<pkg>/page.h`, which declares per-file symbols
named after each file's basename (non-alphanumerics -> '_'):

    extern const char page_html[];      // NUL-terminated file contents
    extern const size_t page_html_len;  // length, excluding the NUL

The generator tool label is anchored to THIS module (via Label()), so the
macro is usable from other Bazel modules without caller-relative paths.
"""

_GEN = Label("//rules:resource_gen.py")

def c_resource_library(name, srcs, **kwargs):
    """Embed `srcs` as C arrays and expose them as cc_library `name`."""
    native.genrule(
        name = name + "_gen",
        srcs = srcs,
        outs = [name + ".h", name + ".c"],
        cmd = ("python3 $(location %s) --name %s --out-dir $(RULEDIR) $(SRCS)" %
               (_GEN, name)),
        tools = [_GEN],
    )
    native.cc_library(
        name = name,
        srcs = [name + ".c"],
        hdrs = [name + ".h"],
        **kwargs
    )
