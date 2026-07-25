#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

PT_LOAD = 1
SHT_NOBITS = 8
SHF_ALLOC = 0x2

def parse(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")

    phoff, shoff = struct.unpack_from("<II", d, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", d, 0x2A)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)

    loads = []
    for i in range(phnum):
        o = phoff + i * phentsize
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", d, o)
        if t == PT_LOAD and fsz:
            loads.append((va, off, fsz))

    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        nm, st, fl, ad, off, sz = struct.unpack_from("<6I", d, o)
        secs.append(dict(name_off=nm, type=st, flags=fl, addr=ad,
                         offset=off, size=sz))
    base = secs[shstrndx]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode()

    return d, loads, secs

def image(d, loads):
    lo = min(va for va, _, _ in loads)
    hi = max(va + fsz for va, _, fsz in loads)
    buf = bytearray(hi - lo)
    covered = bytearray(hi - lo)
    for va, off, fsz in loads:
        buf[va - lo:va - lo + fsz] = d[off:off + fsz]
        covered[va - lo:va - lo + fsz] = b"\x01" * fsz
    return lo, buf, covered

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: verify.py <original> <built>")
    a_path, b_path = Path(sys.argv[1]), Path(sys.argv[2])
    A, aload, asec = parse(a_path)
    B, bload, bsec = parse(b_path)

    alo, abuf, acov = image(A, aload)
    blo, bbuf, bcov = image(B, bload)

    print(f"original: {len(aload)} PT_LOAD, "
          f"vram {alo:#010x}..{alo + len(abuf):#010x}")
    print(f"built:    {len(bload)} PT_LOAD, "
          f"vram {blo:#010x}..{blo + len(bbuf):#010x}")

    named = sorted(
        (s for s in asec
         if s["flags"] & SHF_ALLOC and s["type"] != SHT_NOBITS and s["size"]),
        key=lambda s: s["addr"])

    def which(va):
        for s in named:
            if s["addr"] <= va < s["addr"] + s["size"]:
                return s["name"]
        return "?"

    lo = min(alo, blo)
    hi = max(alo + len(abuf), blo + len(bbuf))

    def runs(pred):
        out, start = [], None
        for va in range(lo, hi):
            if pred(va):
                if start is None:
                    start = va
            elif start is not None:
                out.append((start, va - start))
                start = None
        if start is not None:
            out.append((start, hi - start))
        return out

    def cov(buf, base, va):
        i = va - base
        return 0 <= i < len(buf) and buf[i]

    wrong = runs(lambda va: cov(acov, alo, va) and cov(bcov, blo, va)
                 and abuf[va - alo] != bbuf[va - blo])
    missing = runs(lambda va: cov(acov, alo, va) and not cov(bcov, blo, va))
    extra = runs(lambda va: cov(bcov, blo, va) and not cov(acov, alo, va))

    named = sorted(
        (s for s in asec
         if s["flags"] & SHF_ALLOC and s["type"] != SHT_NOBITS and s["size"]),
        key=lambda s: s["addr"])

    def which(va):
        for s in named:
            if s["addr"] <= va < s["addr"] + s["size"]:
                return s["name"]
        return "(unloaded gap)"

    print()
    if wrong or missing:
        n = sum(k for _, k in wrong)
        m = sum(k for _, k in missing)
        print(f"MISMATCH -- {n} byte(s) wrong, {m} byte(s) missing")
        print()
        by_sec = {}
        for va, k in wrong + missing:
            by_sec.setdefault(which(va), []).append((va, k))
        for name in sorted(by_sec, key=lambda x: by_sec[x][0][0]):
            rs = by_sec[name]
            print(f"  {name:<28} {len(rs)} run(s), "
                  f"{sum(k for _, k in rs)} byte(s)")
            for va, k in rs[:3]:
                ai, bi = va - alo, va - blo
                oa = abuf[ai:ai + min(k, 8)].hex() if 0 <= ai < len(abuf) else "--"
                ob = bbuf[bi:bi + min(k, 8)].hex() if 0 <= bi < len(bbuf) else "--"
                print(f"      {va:#010x} len {k}  orig {oa}  built {ob}")
            if len(rs) > 3:
                print(f"      ... and {len(rs) - 3} more")
        rc = 1
    else:
        print("MATCH -- every byte the original loads is reproduced exactly")
        rc = 0

    if extra:
        tot = sum(k for _, k in extra)
        nonzero = [(va, k) for va, k in extra
                   if any(bbuf[va - blo + i] for i in range(k))]
        print()
        print(f"note: {tot} byte(s) in {len(extra)} run(s) are loaded by the "
              f"build but not by the original")
        for va, k in extra:
            z = "all zero" if (va, k) not in nonzero else "NONZERO"
            print(f"      {va:#010x} len {k}  ({z})")
        if nonzero:
            print("      NONZERO runs are worth investigating -- the build is "
                  "loading real data the original does not.")

    return rc

if __name__ == "__main__":
    sys.exit(main())
