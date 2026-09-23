"""Generate a CMSIS pack lock (default tools/pyocd/packs.lock) from its packs.in.

For each pyOCD target, resolve the CMSIS Device Family Pack that provides it
(vendor / pack / version) via cmsis-pack-manager's index — the same index pyOCD's
`pack find` uses — derive the pack's download URL from the pack's PDSC `<url>`,
download it, and record the sha256. The result is a JSON lock the `cmsis_packs`
module extension (//rules:cmsis_pack.bzl) turns into one repo per pack.

Run:  bazel run //tools/pyocd:update_packs
This writes the lock back into the source tree ($BUILD_WORKSPACE_DIRECTORY). Another
module keeps its own pair of files (paths relative to its workspace root):
  bazel run @firmware//tools/pyocd:update_packs -- --packs-in X/packs.in --lock X/packs.lock

keil.com rate-limits (HTTP 403) after a few full descriptor downloads. To reuse
an existing cmsis-pack-manager cache instead, e.g. the one `pyocd pack find`
fills (macOS: ~/Library/Application Support/cmsis-pack-manager):
  bazel run //tools/pyocd:update_packs -- --index-cache <dir>
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request

from cmsis_pack_manager import Cache


def _slug(vendor, pack):
    return re.sub(r"[^a-z0-9]+", "_", "{}_{}".format(vendor, pack).lower()).strip("_")


def _pack_base_url(pdsc_text):
    # The <url> element of a PDSC is the base URL packs are published under.
    m = re.search(r"<url>\s*(.*?)\s*</url>", pdsc_text, re.IGNORECASE | re.DOTALL)
    if not m:
        raise SystemExit("no <url> in PDSC")
    return m.group(1).strip()


def _find_pdsc(data_path, vendor, pack):
    # cmsis-pack-manager stores PDSCs under data_path; match <vendor>.<pack>*.pdsc.
    want = "{}.{}".format(vendor, pack).lower()
    for root, _dirs, files in os.walk(data_path):
        for f in files:
            if f.lower().endswith(".pdsc") and f.lower().startswith(want):
                return os.path.join(root, f)
    return None


# www.keil.com/pack now 403s every download (Akamai); Arm serves the same files
# from this CDN. Record it first and keep the PDSC's own URL as a fallback.
_KEIL_PACK_BASE = "https://www.keil.com/pack"
_KEIL_PACK_CDN = "https://keilpack.azureedge.net/pack"


def _candidate_urls(base, filename):
    base = base.rstrip("/")
    urls = [base + "/" + filename]
    if base.replace("http://", "https://") == _KEIL_PACK_BASE:
        urls.insert(0, _KEIL_PACK_CDN + "/" + filename)
    return urls


def _download(urls, dest):
    """Fetch the first URL that works; return it."""
    errors = []
    for url in urls:
        print("Downloading {} ...".format(url))
        req = urllib.request.Request(url, headers={"User-Agent": "embedded-update-packs"})
        try:
            with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
            return url
        except OSError as exc:
            errors.append("{}: {}".format(url, exc))
    raise SystemExit("could not download pack:\n  " + "\n  ".join(errors))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if not workspace:
        raise SystemExit("run via `bazel run //tools/pyocd:update_packs`")
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs-in", default="tools/pyocd/packs.in",
                    help="target list, relative to the workspace root")
    ap.add_argument("--lock", default="tools/pyocd/packs.lock",
                    help="lock file to write, relative to the workspace root")
    ap.add_argument("--index-cache", metavar="DIR",
                    help="existing cmsis-pack-manager cache (index.json + PDSCs) to use "
                         "instead of downloading the descriptor set")
    args = ap.parse_args()

    with open(os.path.join(workspace, args.packs_in)) as f:
        targets = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    work = tempfile.mkdtemp(prefix="cmsis-packs-")
    if args.index_cache:
        index_dir = os.path.expanduser(args.index_cache)
        if not os.path.exists(os.path.join(index_dir, "index.json")):
            raise SystemExit("no index.json in {}".format(index_dir))
        print("Resolving {} target(s) via the cached CMSIS index in {}...".format(len(targets), index_dir))
        cache = Cache(True, True, json_path=index_dir, data_path=index_dir)
    else:
        index_dir = work
        print("Resolving {} target(s) via the CMSIS index (this downloads the pack "
              "descriptor set; may take a few minutes)...".format(len(targets)))
        cache = Cache(True, True, json_path=work, data_path=work)
        cache.cache_descriptors()
    index = cache.index
    lower = {name.lower(): name for name in index}

    packs = {}  # slug -> pack dict
    for target in targets:
        dname = lower.get(target.lower())
        if not dname:
            raise SystemExit("target {!r} not found in the CMSIS index".format(target))
        fp = index[dname]["from_pack"]
        vendor, pack, version = fp["vendor"], fp["pack"], fp["version"]
        slug = _slug(vendor, pack)
        entry = packs.setdefault(slug, {
            "slug": slug,
            "vendor": vendor,
            "pack": pack,
            "version": version,
            "targets": [],
        })
        entry["targets"].append(target)

    for entry in packs.values():
        vendor, pack, version = entry["vendor"], entry["pack"], entry["version"]
        pdsc = _find_pdsc(index_dir, vendor, pack)
        if not pdsc:
            raise SystemExit("PDSC for {}.{} not found in cache".format(vendor, pack))
        with open(pdsc, encoding="utf-8", errors="replace") as f:
            base = _pack_base_url(f.read())
        filename = "{}.{}.{}.pack".format(vendor, pack, version)
        urls = _candidate_urls(base, filename)
        dest = os.path.join(work, filename)
        _download(urls, dest)
        entry["urls"] = urls
        entry["filename"] = filename
        entry["sha256"] = _sha256(dest)
        entry["targets"] = sorted(entry["targets"])

    lock = {"packs": sorted(packs.values(), key=lambda e: e["slug"])}
    out = os.path.join(workspace, args.lock)
    with open(out, "w") as f:
        json.dump(lock, f, indent=2)
        f.write("\n")
    print("Wrote {} ({} pack(s)).".format(out, len(lock["packs"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
