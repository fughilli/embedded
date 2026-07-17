"""Macros for protobuf codegen against this module's base support.

The pattern (originally proven on led_mapper's esp32 branch): nothing is
checked in — the hermetic prebuilt protoc emits a FileDescriptorSet at build
time, and a small per-project micropb-gen driver (the single home of that
project's heapless container capacity table) turns it into no_std Rust.
Python bindings come straight from protoc's --python_out.

    load("@firmware//proto:micropb.bzl",
         "micropb_rust_library", "proto_py_gen")

    micropb_rust_library(
        name = "widget_pb",
        proto = "widget.proto",
        gen_main = "gen_main.rs",     # fn main(): fdset, out.rs, profile
        profile = "host",
    )

    proto_py_gen(name = "widget_py_gen", proto = "widget.proto")
    py_library(name = "widget_py_proto", srcs = [":widget_py_gen"],
               imports = ["."], deps = [<pip protobuf>])

The gen_main driver receives (descriptor_set_path, output_path, profile) and
is expected to call micropb_gen's `compile_fdset_file`; the macro prepends
`#![no_std]` to its output so the crate builds for bare-metal targets.
"""

load("@rules_rust//rust:defs.bzl", "rust_binary", "rust_library")

def proto_fdset(name, proto):
    """FileDescriptorSet from a .proto via the hermetic prebuilt protoc."""
    native.genrule(
        name = name,
        srcs = [proto],
        outs = [name + ".bin"],
        cmd = ("$(execpath @firmware//proto:protoc) " +
               "-I $$(dirname $(location " + proto + ")) " +
               "--descriptor_set_out=$@ $(location " + proto + ")"),
        tools = ["@firmware//proto:protoc"],
    )

def proto_py_gen(name, proto):
    """protoc --python_out genrule: emits <proto basename>_pb2.py."""
    base = proto.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    native.genrule(
        name = name,
        srcs = [proto],
        outs = [base + "_pb2.py"],
        cmd = ("$(execpath @firmware//proto:protoc) " +
               "-I $$(dirname $(location " + proto + ")) " +
               "--python_out=$(RULEDIR) $(location " + proto + ")"),
        tools = ["@firmware//proto:protoc"],
    )

def micropb_rust_library(
        name,
        proto,
        gen_main,
        profile = "host",
        crate_name = None,
        visibility = None):
    """no_std Rust (micropb) bindings for a .proto, generated at build time.

    Multiple invocations may share one gen_main and differ only in `profile`
    (e.g. generous host containers vs firmware-sized ones); pass the same
    `crate_name` so downstream code is identical either way, and depend on
    exactly one of them per target.
    """
    fdset = name + "_fdset"
    proto_fdset(fdset, proto)
    gen_bin = name + "_gen_bin"
    rust_binary(
        name = gen_bin,
        srcs = [gen_main],
        edition = "2021",
        deps = ["@firmware//proto:micropb_gen"],
    )
    rs = name + "_rs_gen"
    native.genrule(
        name = rs,
        srcs = [":" + fdset],
        outs = [name + "_gen.rs"],
        cmd = ("$(execpath :" + gen_bin + ") $(location :" + fdset + ") " +
               "$@.body " + profile +
               " && (echo '#![no_std]'; " +
               "echo '#![allow(non_snake_case, non_camel_case_types, unused_mut, clippy::all)]'; " +
               "cat $@.body) > $@ && rm $@.body"),
        tools = [":" + gen_bin],
    )
    rust_library(
        name = name,
        srcs = [":" + rs],
        crate_name = crate_name,
        crate_root = ":" + rs,
        edition = "2021",
        visibility = visibility,
        deps = ["@firmware//proto:micropb"],
    )
