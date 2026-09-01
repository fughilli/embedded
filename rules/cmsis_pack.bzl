"""Hermetic CMSIS-Pack (Device Family Pack) support for pyOCD.

A pyOCD `--target` outside pyOCD's built-ins lives in a CMSIS Device Family Pack
(a `.pack`, i.e. a zip of device descriptions + flash algorithms). This ruleset
fetches locked packs and wires them into //tools/pyocd, mirroring how
rules_python turns a requirements lock into per-wheel repos + a hub:

    packs.in (targets)  --bazel run :update_packs-->  packs.lock  (url + sha256)
    packs.lock          --cmsis_packs extension-->    one @cmsis_pack_<slug> repo
                                                       per pack (downloaded) +
                                                       a @cmsis_packs hub
    //tools/pyocd:pyocd  --data--> @cmsis_packs//:all_packs, auto-`--pack`ed at run

The lock is JSON so both the generator (Python) and this extension
(`json.decode`) read it. Regenerate: `bazel run //tools/pyocd:update_packs`.
"""

# --- one repo per pack: download the .pack, pinned by sha256 -----------------
def _cmsis_pack_repo_impl(rctx):
    rctx.download(
        url = rctx.attr.urls,
        output = rctx.attr.filename,
        sha256 = rctx.attr.sha256,
    )
    rctx.file("BUILD.bazel", _PACK_BUILD.format(filename = rctx.attr.filename))

_PACK_BUILD = """\
package(default_visibility = ["//visibility:public"])

exports_files(["{filename}"])

filegroup(name = "pack", srcs = ["{filename}"])
"""

cmsis_pack_repo = repository_rule(
    implementation = _cmsis_pack_repo_impl,
    doc = "Download a single CMSIS .pack, pinned by sha256.",
    attrs = {
        "urls": attr.string_list(mandatory = True),
        "sha256": attr.string(mandatory = True),
        "filename": attr.string(mandatory = True),
    },
)

# --- hub: gather every pack into one repo (packs/<file>.pack) ----------------
# Symlinking the sibling pack repos' files here makes the whole set live under a
# single repo, so //tools/pyocd can depend on one filegroup and find the packs in
# its runfiles by a simple glob (no canonical-repo-name juggling).
def _cmsis_pack_hub_impl(rctx):
    filenames = []
    for pack in rctx.attr.packs:
        src = rctx.path(pack)
        rctx.symlink(src, "packs/" + src.basename)
        filenames.append(src.basename)
    rctx.file("BUILD.bazel", _HUB_BUILD)
    rctx.file("packs.bzl", "CMSIS_PACK_FILES = {}\n".format(repr(sorted(filenames))))

_HUB_BUILD = """\
package(default_visibility = ["//visibility:public"])

# Every locked .pack, as runfiles for //tools/pyocd (auto-passed via --pack).
filegroup(
    name = "all_packs",
    srcs = glob(["packs/**"], allow_empty = True),
)
"""

cmsis_pack_hub = repository_rule(
    implementation = _cmsis_pack_hub_impl,
    doc = "Aggregate all pack repos into packs/ under one hub repo.",
    attrs = {"packs": attr.label_list(allow_files = True)},
)

# --- module extension: packs.lock -> per-pack repos + hub --------------------
def _cmsis_impl(mctx):
    for mod in mctx.modules:
        for parse in mod.tags.parse:
            lock = json.decode(mctx.read(parse.lock))
            pack_labels = []
            for pack in lock["packs"]:
                repo = "cmsis_pack_" + pack["slug"]
                cmsis_pack_repo(
                    name = repo,
                    urls = [pack["url"]],
                    sha256 = pack["sha256"],
                    filename = pack["filename"],
                )
                pack_labels.append("@{}//:{}".format(repo, pack["filename"]))
            cmsis_pack_hub(name = parse.hub_name, packs = pack_labels)

cmsis_packs = module_extension(
    implementation = _cmsis_impl,
    doc = "Instantiate CMSIS packs from a lockfile (see //tools/pyocd:packs.lock).",
    tag_classes = {
        "parse": tag_class(attrs = {
            "lock": attr.label(mandatory = True, doc = "JSON pack lockfile."),
            "hub_name": attr.string(default = "cmsis_packs"),
        }),
    },
)
