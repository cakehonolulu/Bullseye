#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

SHT_NOBITS = 8

def parse(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")

    h = {}
    (h["type"], h["machine"], h["version"], h["entry"], h["phoff"],
     h["shoff"], h["flags"], h["ehsize"], h["phentsize"], h["phnum"],
     h["shentsize"], h["shnum"], h["shstrndx"]) = struct.unpack_from(
        "<HHIIIIIHHHHHH", d, 0x10)

    phdrs = []
    for i in range(h["phnum"]):
        o = h["phoff"] + i * h["phentsize"]
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", d, o)
        phdrs.append(dict(type=t, offset=off, vaddr=va, filesz=fsz,
                          memsz=msz, flags=fl, align=al))

    secs = []
    for i in range(h["shnum"]):
        o = h["shoff"] + i * h["shentsize"]
        (nm, st, fl, ad, off, sz, lk, inf, al, ent) = struct.unpack_from(
            "<10I", d, o)
        secs.append(dict(name_off=nm, type=st, flags=fl, addr=ad,
                         offset=off, size=sz, align=al))
    base = secs[h["shstrndx"]]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode()

    return d, h, phdrs, secs

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: diffbin.py <original> <built>")
    a_path, b_path = Path(sys.argv[1]), Path(sys.argv[2])
    A, ah, aph, asec = parse(a_path)
    B, bh, bph, bsec = parse(b_path)

    print(f"size   orig {len(A):#x} ({len(A)})   built {len(B):#x} ({len(B)})"
          f"   delta {len(B) - len(A):+d}")
    print()

    print("=== ELF header ===")
    same = True
    for k in ah:
        if ah[k] != bh[k]:
            print(f"  {k:<10} orig {ah[k]:#x}   built {bh[k]:#x}")
            same = False
    print("  identical" if same else "")
    print()

    print("=== program headers ===")
    print(f"  orig {len(aph)}, built {len(bph)}")
    for i in range(max(len(aph), len(bph))):
        x = aph[i] if i < len(aph) else None
        y = bph[i] if i < len(bph) else None
        if x != y:
            print(f"  [{i}] orig  {x}")
            print(f"      built {y}")
    print()

    an = {s["name"]: s for s in asec}
    bn = {s["name"]: s for s in bsec}

    only_a = [n for n in an if n not in bn]
    only_b = [n for n in bn if n not in an]
    print("=== sections present in only one file ===")
    for n in only_a:
        print(f"  orig only:  {n:<24} size {an[n]['size']:#x}")
    for n in only_b:
        print(f"  built only: {n:<24} size {bn[n]['size']:#x}")
    if not only_a and not only_b:
        print("  none")
    print()

    print("=== sections differing in placement or size ===")
    any_diff = False
    for n in an:
        if n not in bn:
            continue
        x, y = an[n], bn[n]
        bits = []
        for f in ("addr", "offset", "size", "align", "flags", "type"):
            if x[f] != y[f]:
                bits.append(f"{f} {x[f]:#x}->{y[f]:#x}")
        if bits:
            any_diff = True
            print(f"  {n:<26} {', '.join(bits)}")
    if not any_diff:
        print("  none")
    print()

    print("=== content differences (sections at matching offset/size) ===")
    clean = True
    for n in sorted(an, key=lambda k: an[k]["offset"]):
        if n not in bn:
            continue
        x, y = an[n], bn[n]
        if x["type"] == SHT_NOBITS or x["size"] == 0:
            continue
        if (x["offset"], x["size"]) != (y["offset"], y["size"]):
            continue
        sa = A[x["offset"]:x["offset"] + x["size"]]
        sb = B[y["offset"]:y["offset"] + y["size"]]
        if sa == sb:
            continue
        clean = False
        runs, start = [], None
        for i in range(len(sa)):
            if sa[i] != sb[i]:
                if start is None:
                    start = i
            elif start is not None:
                runs.append((start, i))
                start = None
        if start is not None:
            runs.append((start, len(sa)))
        total = sum(e - s for s, e in runs)
        print(f"  {n:<26} {len(runs)} run(s), {total} byte(s) differ "
              f"({100.0 * total / len(sa):.4f}%)")
        for s, e in runs[:5]:
            va = x["addr"] + s
            print(f"      +{s:#08x} (vram {va:#010x}) len {e - s}"
                  f"  orig {sa[s:min(e, s + 8)].hex()}"
                  f"  built {sb[s:min(e, s + 8)].hex()}")
        if len(runs) > 5:
            print(f"      ... and {len(runs) - 5} more run(s)")
    if clean:
        print("  none -- all comparable sections are byte-identical")

if __name__ == "__main__":
    main()
