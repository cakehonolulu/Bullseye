#!/usr/bin/env python3
import hashlib
import json
import struct
import sys
from pathlib import Path

SHT_NOBITS = 8
SHF_ALLOC = 0x2

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: extract_container.py <original> <outdir>")
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    d = bytearray(src.read_bytes())
    if d[:4] != b"\x7fELF":
        sys.exit(f"{src}: not an ELF")

    sha1 = hashlib.sha1(bytes(d)).hexdigest()
    phoff, shoff = struct.unpack_from("<II", d, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", d, 0x2A)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)

    secs = []
    for i in range(shnum):
        nm, st, fl, ad, off, sz = struct.unpack_from(
            "<6I", d, shoff + i * shentsize)
        secs.append(dict(idx=i, name_off=nm, type=st, flags=fl,
                         addr=ad, offset=off, size=sz))
    base = secs[shstrndx]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode()

    regions = []
    for s in secs:
        if s["type"] == SHT_NOBITS or not s["size"]:
            continue
        if not s["flags"] & SHF_ALLOC:
            continue
        regions.append(dict(name=s["name"], offset=s["offset"],
                            size=s["size"], vaddr=s["addr"]))
    regions.sort(key=lambda r: r["offset"])

    prev = None
    for r in regions:
        if prev and r["offset"] < prev["offset"] + prev["size"]:
            sys.exit(f"overlapping allocated sections: "
                     f"{prev['name']} and {r['name']}")
        prev = r

    built = sum(r["size"] for r in regions)
    for r in regions:
        d[r["offset"]:r["offset"] + r["size"]] = b"\x00" * r["size"]

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "template.bin").write_bytes(bytes(d))
    (outdir / "manifest.json").write_text(json.dumps(
        dict(source=src.name, sha1=sha1, file_size=len(d),
             regions=regions), indent=1) + "\n")

    carried = len(d) - built
    print(f"template  {outdir / 'template.bin'}")
    print(f"manifest  {outdir / 'manifest.json'}")
    print(f"sha1      {sha1}")
    print()
    print(f"{len(regions)} allocated section(s), {built:#x} bytes "
          f"({100.0 * built / len(d):.1f}%) supplied by the build")
    print(f"{carried:#x} bytes ({100.0 * carried / len(d):.1f}%) carried: "
          f"headers, section table, .shstrtab, and non-allocated sections")

    nonalloc = [s for s in secs
                if s["size"] and s["type"] != SHT_NOBITS
                and not s["flags"] & SHF_ALLOC]
    if nonalloc:
        by = {}
        for s in nonalloc:
            k = ".".join(s["name"].split(".")[:2]) or s["name"]
            by[k] = by.get(k, 0) + s["size"]
        print()
        print("carried non-allocated content (real game data, not yet built):")
        for k, sz in sorted(by.items(), key=lambda kv: -kv[1]):
            print(f"    {k}.*  {sz:#x} bytes")

if __name__ == "__main__":
    main()
