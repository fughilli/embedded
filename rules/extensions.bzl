"""Module extension wrapping `arduino_library` so add-on Arduino libraries can
be declared as tags in MODULE.bazel and `use_repo`'d.
"""

load(":arduino_library.bzl", "arduino_library")

def _arduino_impl(module_ctx):
    for mod in module_ctx.modules:
        for lib in mod.tags.library:
            arduino_library(
                name = lib.name,
                url = lib.url,
                urls = lib.urls,
                sha256 = lib.sha256,
                strip_prefix = lib.strip_prefix,
                lib_name = lib.lib_name or lib.name,
                src_dirs = lib.src_dirs,
                copts = lib.copts,
                defines = lib.defines,
                deps = lib.deps,
            )

_library = tag_class(attrs = {
    "name": attr.string(mandatory = True),
    "url": attr.string(),
    "urls": attr.string_list(),
    "sha256": attr.string(),
    "strip_prefix": attr.string(),
    "lib_name": attr.string(),
    "src_dirs": attr.string_list(default = ["src"]),
    "copts": attr.string_list(default = []),
    "defines": attr.string_list(default = []),
    "deps": attr.string_list(default = []),
})

arduino = module_extension(
    implementation = _arduino_impl,
    tag_classes = {"library": _library},
)
