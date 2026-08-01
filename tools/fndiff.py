#!/usr/bin/env python3
import argparse
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PT_LOAD = 1
SHT_SYMTAB = 2
STT_FUNC = 2
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHN_UNDEF = 0
SHN_ABS = 0xFFF1
SHN_COMMON = 0xFFF2

NAME_RE = re.compile(r"^func_([0-9A-Fa-f]{8})$")
SYMADDR_RE = re.compile(
    r"^\s*([A-Za-z_$.][\w$.]*)\s*=\s*(0x[0-9A-Fa-f]+)\s*;(.*)$")

MAP_RE = re.compile(
    r"^\s*(?:\.\S+\s+)?0x0*([0-9a-fA-F]+)\s+0x0*([0-9a-fA-F]+)\s+"
    r"(\S+\.o\)?)\s*$")

def read_elf(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")
    if d[4] != 1 or d[5] != 1:
        sys.exit(f"{path}: expected ELF32 little-endian")
    return d

def sections(d):
    shoff = struct.unpack_from("<I", d, 0x20)[0]
    shentsize, shnum = struct.unpack_from("<HH", d, 0x2E)
    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        nm, st, fl, ad, off, sz, lk, inf, al, ent = struct.unpack_from(
            "<10I", d, o)
        secs.append(dict(type=st, flags=fl, addr=ad, offset=off, size=sz,
                         link=lk, entsize=ent))
    return secs

def functions(d):
    secs = sections(d)
    raw = {}
    for s in secs:
        if s["type"] != SHT_SYMTAB:
            continue
        strtab = secs[s["link"]]
        ent = s["entsize"] or 16
        for i in range(s["size"] // ent):
            o = s["offset"] + i * ent
            name_off, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", d, o)
            if (info & 0xF) != STT_FUNC:
                continue
            if shndx in (SHN_UNDEF, SHN_ABS, SHN_COMMON) or shndx >= len(secs):
                continue
            host = secs[shndx]
            if not (host["flags"] & SHF_ALLOC and host["flags"] & SHF_EXECINSTR):
                continue
            e = d.index(b"\0", strtab["offset"] + name_off)
            name = d[strtab["offset"] + name_off:e].decode(errors="replace")
            if name:
                raw.setdefault(name, []).append(
                    (value, size, host["addr"] + host["size"]))

    starts = sorted({v for e in raw.values() for v, _, _ in e})
    nxt = {a: b for a, b in zip(starts, starts[1:])}

    out, dup = {}, {}
    for name, entries in raw.items():
        fixed = set()
        for value, size, end in entries:
            if not size:
                size = min(nxt.get(value, end), end) - value
            fixed.add((value, max(size, 0)))
        if len(fixed) == 1:
            out[name] = next(iter(fixed))
        else:
            dup[name] = sorted(fixed)
    return out, dup

def load_image(d, path):
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
    return lo, bytes(buf), bytes(cov)

def expected_map(orig_bytes, symbol_addrs):
    exp = {}
    src = "func_ name"

    if symbol_addrs and symbol_addrs.is_file():
        n = 0
        for line in symbol_addrs.read_text(errors="replace").splitlines():
            line = line.split("//", 1)[0] if line.strip().startswith("//") \
                else line
            m = SYMADDR_RE.match(line)
            if m and "type:func" in (m.group(3) or ""):
                exp[m.group(1)] = int(m.group(2), 16)
                n += 1
        if n:
            src = f"{symbol_addrs.name} ({n})"

    got, _ = functions(orig_bytes)
    if got:
        for name, (addr, _size) in got.items():
            exp[name] = addr
        src = f"original symbol table ({len(got)})"

    return exp, src

def map_index(path):
    if not path or not path.is_file():
        return []
    spans = []
    for line in path.read_text(errors="replace").splitlines():
        m = MAP_RE.match(line)
        if not m:
            continue
        addr, size = int(m.group(1), 16), int(m.group(2), 16)
        if size:
            spans.append((addr, addr + size, m.group(3)))
    spans.sort()
    return spans

def owner(spans, addr):
    lo, hi = 0, len(spans)
    while lo < hi:
        mid = (lo + hi) // 2
        if spans[mid][0] <= addr:
            lo = mid + 1
        else:
            hi = mid
    if lo and spans[lo - 1][1] > addr:
        return spans[lo - 1][2]
    return None

def divergences(rows):
    events = []
    prev_delta = 0
    prev = None
    for i, r in enumerate(rows):
        delta = r[1] - r[0]
        if delta != prev_delta:
            events.append(dict(index=i, first=r, culprit=prev,
                               change=delta - prev_delta, delta=delta))
        prev_delta = delta
        prev = r
    for j, ev in enumerate(events):
        end = events[j + 1]["index"] if j + 1 < len(events) else len(rows)
        ev["shifted"] = end - ev["index"]
    return events

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original", type=Path)
    ap.add_argument("built", type=Path)
    ap.add_argument("--map", type=Path, default=None,
                    help="linker map (default: <built>.map)")
    ap.add_argument("--symbols", type=Path,
                    default=ROOT / "config" / "symbol_addrs.txt")
    ap.add_argument("--top", type=int, default=8,
                    help="how many divergences to detail (default 8)")
    ap.add_argument("--all", action="store_true",
                    help="list every shifted function, the old behaviour")
    ap.add_argument("--content", action="store_true",
                    help="also check bytes of correctly-placed functions")
    args = ap.parse_args()

    O = read_elf(args.original)
    B = read_elf(args.built)

    exp, exp_src = expected_map(O, args.symbols)
    built, dup = functions(B)

    rows = []
    unknown = 0
    for name, (addr, size) in built.items():
        want = exp.get(name)
        if want is None:
            m = NAME_RE.match(name)
            if not m:
                unknown += 1
                continue
            want = int(m.group(1), 16)
        rows.append((want, addr, name, size))
    if not rows:
        sys.exit("no functions with a known expected address")
    rows.sort()

    mapfile = args.map or Path(str(args.built) + ".map")
    spans = map_index(mapfile)

    def where(addr):
        o = owner(spans, addr)
        return o or "?"

    events = divergences(rows)

    if not events and not args.content:
        return 0

    if events:
        moved = sum(e["shifted"] for e in events)
        print(f"fndiff: {len(events)} divergence(s); {moved} of {len(rows)} "
              f"function(s) are displaced as a result")
        print(f"        expected addresses from {exp_src}")
        if not spans:
            print(f"        (no {mapfile.name} -- object attribution off)")
        print()

    for k, ev in enumerate(events[:args.top]):
        first = ev["first"]
        culprit = ev["culprit"]
        obj = where(culprit[1]) if culprit else where(first[1])
        print(f"[{k + 1}] {obj}")
        if culprit:
            grew = first[0] - culprit[0]          # original span
            got = first[1] - culprit[1]           # built span
            print(f"    {culprit[2]} occupies {got:#x} bytes, "
                  f"the original gives it {grew:#x}  ({ev['change']:+d})")
        else:
            print(f"    everything before {first[2]} is "
                  f"{ev['change']:+d} bytes off")
        print(f"    from {first[2]} @ {first[0]:#010x} onward, "
              f"{ev['shifted']} function(s) sit at {ev['delta']:+d}")
        print()

    if len(events) > args.top:
        print(f"... and {len(events) - args.top} more divergence(s). "
              f"Fix [1] and re-run; later ones are often the same bug.\n")

    if args.all:
        print("every displaced function:")
        for want, addr, name, size in rows:
            if want != addr:
                print(f"  {name:<28} expected {want:#010x}  "
                      f"actual {addr:#010x}  ({addr - want:+d})")
        print()

    if args.content:
        olo, obuf, ocov = load_image(O, args.original)
        blo, bbuf, bcov = load_image(B, args.built)

        def grab(buf, cov, base, va, n):
            i = va - base
            if i < 0 or i + n > len(buf) or not all(cov[i:i + n]):
                return None
            return buf[i:i + n]

        bad = []
        for want, addr, name, size in rows:
            if want != addr or not size:
                continue
            a = grab(obuf, ocov, olo, addr, size)
            b = grab(bbuf, bcov, blo, addr, size)
            if a is not None and a != b:
                bad.append((addr, name, size, a, b))

        if bad:
            by_obj = {}
            for addr, name, size, a, b in bad:
                by_obj.setdefault(where(addr), []).append(
                    (addr, name, size, a, b))
            print(f"CONTENT: {len(bad)} function(s) at the right address "
                  f"with the wrong bytes, in {len(by_obj)} object(s)\n")
            for obj in sorted(by_obj, key=lambda o: by_obj[o][0][0]):
                items = by_obj[obj]
                print(f"  {obj}  ({len(items)})")
                for addr, name, size, a, b in items[:5]:
                    n = min(len(a), 8)
                    print(f"      {name:<26} @ {addr:#010x} size {size:#x}")
                    print(f"      {'':26}   orig  {a[:n].hex()}")
                    print(f"      {'':26}   built {(b or b'')[:n].hex()}")
                if len(items) > 5:
                    print(f"      ... and {len(items) - 5} more")
                print()

    if dup:
        named = {n: e for n, e in dup.items() if n in exp or NAME_RE.match(n)}
        if named:
            print(f"note: {len(named)} name(s) have conflicting symbol table "
                  f"entries and were skipped")

    if unknown:
        print(f"note: {unknown} function(s) have no expected address "
              f"(add them to {args.symbols.name} to cover them)")

    return 1 if events else 0

if __name__ == "__main__":
    sys.exit(main())
