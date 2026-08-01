#!/usr/bin/env python3
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHT_SYMTAB = 2
SHT_NOBITS = 8
STT_FUNC = 2
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHN_UNDEF = 0

def read(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")

    shoff = struct.unpack_from("<I", d, 0x20)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)
    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        nm, st, fl, ad, off, sz, lk, inf, al, ent = struct.unpack_from(
            "<10I", d, o)
        secs.append(dict(name_off=nm, type=st, flags=fl, addr=ad, offset=off,
                         size=sz, link=lk, entsize=ent))
    base = secs[shstrndx]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode(errors="replace")
    return d, secs

def section_sizes(secs):
    out = {}
    for s in secs:
        if not s["size"] or not s["flags"] & SHF_ALLOC:
            continue
        n = s["name"]
        if n.startswith(".gnu.linkonce.t."):
            key = ".text"
        elif n.startswith(".gnu.linkonce.d."):
            key = ".data"
        elif n.startswith(".gnu.linkonce.r."):
            key = ".rodata"
        else:
            key = "." + n.lstrip(".").split(".")[0]
        out[key] = out.get(key, 0) + s["size"]
    return out

def func_sizes(d, secs):
    per_sec = {}
    for s in secs:
        if s["type"] != SHT_SYMTAB:
            continue
        strtab = secs[s["link"]]
        ent = s["entsize"] or 16
        for i in range(s["size"] // ent):
            o = s["offset"] + i * ent
            name_off, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", d, o)
            if (info & 0xF) != STT_FUNC or shndx == SHN_UNDEF:
                continue
            if shndx >= len(secs):
                continue
            host = secs[shndx]
            if not host["flags"] & SHF_EXECINSTR:
                continue
            e = d.index(b"\0", strtab["offset"] + name_off)
            name = d[strtab["offset"] + name_off:e].decode(errors="replace")
            if name:
                per_sec.setdefault(shndx, []).append((value, size, name))

    out = {}
    for shndx, entries in per_sec.items():
        end = secs[shndx]["size"]
        entries.sort()
        for j, (value, size, name) in enumerate(entries):
            if not size:
                nxt = entries[j + 1][0] if j + 1 < len(entries) else end
                size = max(nxt - value, 0)
            out[name] = size
    return out

def units(root, only):
    cfg = root / "objdiff.json"
    if cfg.is_file():
        data = json.loads(cfg.read_text())
        rows = [(u["name"], root / u["target_path"], root / u["base_path"])
                for u in data.get("units", [])]
    else:
        rows = []
        tdir = root / "build" / "target"
        if not tdir.is_dir():
            sys.exit("no objdiff.json and no build/target -- "
                     "run configure.py first")
        for t in sorted(tdir.glob("*.o")):
            hits = sorted((root / "build" / "src").rglob(f"{t.stem}.*.o"))
            if hits:
                rows.append((t.stem, t, hits[0]))
    if only:
        want = set(only)
        rows = [r for r in rows if r[0] in want]
        if not rows:
            sys.exit(f"no unit matched {', '.join(only)}")
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unit", nargs="*", help="limit to these units")
    ap.add_argument("--bytes", action="store_true",
                    help="also report same-size functions with differing bytes")
    ap.add_argument("--quiet", action="store_true",
                    help="one line per bad unit, no function detail")
    args = ap.parse_args()

    rows = units(ROOT, args.unit)
    if not rows:
        sys.exit("no units configured")

    checked = skipped = 0
    bad = []

    for name, tpath, bpath in rows:
        if not tpath.is_file() or not bpath.is_file():
            skipped += 1
            continue
        checked += 1
        td, tsecs = read(tpath)
        bd, bsecs = read(bpath)

        tsz, bsz = section_sizes(tsecs), section_sizes(bsecs)
        secdiff = [(k, tsz.get(k, 0), bsz.get(k, 0))
                   for k in sorted(set(tsz) | set(bsz))
                   if tsz.get(k, 0) != bsz.get(k, 0)]

        tf, bf = func_sizes(td, tsecs), func_sizes(bd, bsecs)
        fndiff = [(k, tf.get(k), bf.get(k))
                  for k in sorted(set(tf) | set(bf))
                  if tf.get(k) != bf.get(k)]

        if secdiff or fndiff:
            delta = sum(b - t for _, t, b in secdiff)
            bad.append((name, delta, secdiff, fndiff))

    if not bad:
        print(f"unitdiff: all {checked} unit(s) match the target in size"
              + (f" ({skipped} not built)" if skipped else ""))
        return 0

    bad.sort(key=lambda r: (-abs(r[1]), r[0]))
    print(f"unitdiff: {len(bad)} of {checked} unit(s) differ in size"
          + (f" ({skipped} not built)" if skipped else ""))
    print()

    for name, delta, secdiff, fndiff in bad:
        parts = ", ".join(f"{k} {t:#x} -> {b:#x} ({b - t:+d})"
                          for k, t, b in secdiff) or "sections match"
        print(f"  {name:<24} {parts}")
        if args.quiet:
            continue
        for fn, t, b in fndiff[:12]:
            if t is None:
                print(f"      {fn:<30} only in the build ({b:#x})")
            elif b is None:
                print(f"      {fn:<30} missing from the build ({t:#x})")
            else:
                print(f"      {fn:<30} {t:#x} -> {b:#x}  ({b - t:+d})")
        if len(fndiff) > 12:
            print(f"      ... and {len(fndiff) - 12} more")
        print()

    return 1

if __name__ == "__main__":
    sys.exit(main())
