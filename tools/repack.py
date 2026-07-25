#!/usr/bin/env python3
import hashlib
import json
import struct
import sys
from pathlib import Path

PT_LOAD = 1

def load_image(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")
    phoff = struct.unpack_from("<I", d, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", d, 0x2A)

    spans = []
    for i in range(phnum):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from(
            "<8I", d, phoff + i * phentsize)
        if t == PT_LOAD and fsz:
            spans.append((va, d[off:off + fsz]))
    if not spans:
        sys.exit(f"{path}: no loadable segments")

    lo = min(va for va, _ in spans)
    hi = max(va + len(b) for va, b in spans)
    buf = bytearray(hi - lo)
    cov = bytearray(hi - lo)
    for va, b in spans:
        buf[va - lo:va - lo + len(b)] = b
        cov[va - lo:va - lo + len(b)] = b"\x01" * len(b)
    return lo, buf, cov

def main():
    if len(sys.argv) != 4:
        sys.exit("usage: repack.py <container dir> <linked elf> <output>")
    cdir, linked, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

    manifest = json.loads((cdir / "manifest.json").read_text())
    data = bytearray((cdir / "template.bin").read_bytes())
    if len(data) != manifest["file_size"]:
        sys.exit("template.bin does not match manifest file_size -- "
                 "re-run extract_container.py")

    lo, img, cov = load_image(linked)

    missing = []
    for r in manifest["regions"]:
        va, size, off = r["vaddr"], r["size"], r["offset"]
        i = va - lo
        if i < 0 or i + size > len(img) or not all(cov[i:i + size]):
            missing.append(r)
            continue
        data[off:off + size] = img[i:i + size]

    if missing:
        print(f"ERROR: {len(missing)} region(s) not loaded by "
              f"{linked}:", file=sys.stderr)
        for r in missing[:10]:
            print(f"    {r['name']:<28} vram {r['vaddr']:#010x} "
                  f"size {r['size']:#x}", file=sys.stderr)
        if len(missing) > 10:
            print(f"    ... and {len(missing) - 10} more", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(data))

    got = hashlib.sha1(bytes(data)).hexdigest()
    want = manifest["sha1"]
    print(f"{out}")
    print(f"  sha1     {got}")
    print(f"  expected {want}")
    if got == want:
        print("  OK -- byte-identical to the original")
        return 0

    print("  MISMATCH -- the built image differs from the original.",
          file=sys.stderr)
    print("  Run: python3 tools/verify.py <original> " + str(linked),
          file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
