#!/usr/bin/env python3
import argparse
import bisect
import re
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHT_NOBITS = 8
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4

T_PREFIX = ".gnu.linkonce.t."
VT_PREFIX = ".gnu.linkonce.d._vt$"

MIN_SHARED = 3

LEN_RE = re.compile(r"^(\d+)")

def read_sections(path: Path):
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
        secs.append(dict(name_off=nm, type=st, flags=fl, addr=ad,
                         offset=off, size=sz))
    base = secs[shstrndx]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode(errors="replace")
    return d, secs

def take_class(s):
    m = LEN_RE.match(s)
    if not m:
        return None, s
    n = int(m.group(1))
    body = s[len(m.group(1)):]
    if len(body) < n:
        return None, s
    return body[:n], body[n:]

def split_member(mangled):
    if mangled.startswith("_$_"):
        cls, _ = take_class(mangled[3:])
        return ("~dtor", cls, "") if cls else None
    if mangled.startswith("__tf"):
        cls, _ = take_class(mangled[4:])
        return ("__tf", cls, "") if cls else None

    idx = mangled.find("__")
    if idx < 0:
        return None
    method, rest = mangled[:idx], mangled[idx + 2:]
    if not rest:
        return None
    quals = ""
    while rest and rest[0] in "CVU":
        quals, rest = quals + rest[0], rest[1:]
    if rest[:1] in ("F", "H"):
        return None
    cls, after = take_class(rest)
    if not cls:
        return None
    return (method or "~ctor"), cls, quals + "|" + after

def remangle(method, cls, suffix):
    quals, _, args = suffix.partition("|")
    if method == "~dtor":
        return f"_$_{len(cls)}{cls}"
    if method == "__tf":
        return f"__tf{len(cls)}{cls}"
    if method == "~ctor":
        return f"__{len(cls)}{cls}{args}"
    return f"{method}__{quals}{len(cls)}{cls}{args}"

def demangle_all(names, tool):
    if not names:
        return {}
    payload = "\n".join(names) + "\n"
    for cmd in ([[tool]] if tool else []) + [
            ["c++filt", "--format=gnu", "--no-strip-underscore"],
            ["c++filt", "--format=gnu"]]:
        try:
            r = subprocess.run(cmd, input=payload, capture_output=True,
                               text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            continue
        lines = r.stdout.splitlines()
        if len(lines) == len(names):
            got = {m: x for m, x in zip(names, lines) if x and x != m}
            if got:
                return got
    if not tool:
        return {}
    out = {}
    for n in names:
        try:
            r = subprocess.run([tool, n], capture_output=True, text=True,
                               timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            break
        t = r.stdout.strip()
        if t and t != n:
            out[n] = t
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf", type=Path)
    ap.add_argument("--classes", action="store_true")
    ap.add_argument("--vtables", action="store_true")
    ap.add_argument("--unknown", action="store_true")
    ap.add_argument("--clusters", action="store_true",
                    help="address range per class -- candidate file splits")
    ap.add_argument("--yaml", action="store_true",
                    help="emit splat subsegment lines from the clusters")
    ap.add_argument("--funcs", type=Path,
                    default=ROOT / "asm" / "nonmatchings",
                    help="where to read real function starts from")
    ap.add_argument("--gap", type=lambda s: int(s, 0), default=0x4000,
                    help="max gap within a class's dense core "
                         "(default 0x4000)")
    ap.add_argument("--write-symbols", action="store_true")
    ap.add_argument("--symbols-path", type=Path,
                    default=ROOT / "config" / "symbol_addrs.txt")
    ap.add_argument("--demangle", metavar="TOOL", nargs="?", const="")
    args = ap.parse_args()

    d, secs = read_sections(args.elf)

    lo = hi = None
    for s in secs:
        if s["flags"] & SHF_ALLOC and s["flags"] & SHF_EXECINSTR and s["size"]:
            a, b = s["addr"], s["addr"] + s["size"]
            lo = a if lo is None else min(lo, a)
            hi = b if hi is None else max(hi, b)

    funcs, vtables = {}, {}
    for s in secs:
        if s["name"].startswith(T_PREFIX) and s["size"]:
            funcs[s["addr"]] = s["name"][len(T_PREFIX):]
        elif s["name"].startswith(VT_PREFIX) and s["size"]:
            if s["type"] == SHT_NOBITS:
                continue
            cls, _rest = take_class(s["name"][len(VT_PREFIX):])
            if cls:
                vtables[cls] = (s["addr"],
                                d[s["offset"]:s["offset"] + s["size"]])

    print(f"{args.elf}")
    print(f"  executable   {lo:#010x}..{hi:#010x}")
    print(f"  linkonce fn  {len(funcs)}")
    print(f"  vtables      {len(vtables)}")

    at4 = at0 = 0
    for _, blob in vtables.values():
        for off in range(0, len(blob) - 3, 4):
            (p,) = struct.unpack_from("<I", blob, off)
            if lo <= p < hi:
                if off % 8 == 4:
                    at4 += 1
                else:
                    at0 += 1
    total = at4 + at0
    print(f"  pointers     {total}  ({at4} at offset%8==4, {at0} at ==0)")
    if total and at4 / total > 0.9:
        stride, ptr_off = 8, 4
        print("               -> 8-byte entries {delta,index,pfn}")
    elif total and at0 / total > 0.9:
        stride, ptr_off = 4, 0
        print("               -> 4-byte entries, bare pointers")
    else:
        stride, ptr_off = 8, 4
        print("               -> MIXED; assuming 8-byte. Treat everything "
              "below with suspicion.")
    print()

    slots = {}
    for cls, (vaddr, blob) in vtables.items():
        e = []
        for i in range(0, len(blob) - ptr_off - 3, stride):
            (p,) = struct.unpack_from("<I", blob, i + ptr_off)
            if lo <= p < hi:
                e.append((i // stride, p, funcs.get(p)))
        slots[cls] = e

    named = sum(1 for e in slots.values() for _, _, n in e if n)
    unknown = [(c, s, a) for c, e in slots.items() for s, a, n in e if not n]
    print(f"vtable slots: {named} named, {len(unknown)} unnamed")

    entry_sets = {c: {(s, a) for s, a, _ in e} for c, e in slots.items()}
    related = defaultdict(set)
    keys = list(entry_sets)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if len(entry_sets[a] & entry_sets[b]) >= MIN_SHARED:
                related[a].add(b)
                related[b].add(a)
    pairs = sum(len(v) for v in related.values()) // 2

    proposals = {}
    for cls, slot, addr in unknown:
        cands = set()
        for other in related.get(cls, ()):
            for s, _a, nm in slots[other]:
                if s == slot and nm:
                    p = split_member(nm)
                    if p:
                        cands.add((p[0], p[2]))
        if len(cands) == 1:
            method, suffix = next(iter(cands))
            proposals[addr] = (remangle(method, cls, suffix), cls, slot)

    print(f"proposals:    {len(proposals)} from {pairs} related class "
          f"pair(s) (>= {MIN_SHARED} shared entries)")
    print()

    dem = {}
    if args.demangle is not None:
        pool = sorted(set(funcs.values()) | {v[0] for v in proposals.values()})
        dem = demangle_all(pool, args.demangle or None)
        print(f"{len(dem)} name(s) demangled\n" if dem
              else "demangler produced nothing\n")

    def show(n):
        return dem.get(n, n)

    tail_start = min(funcs) if funcs else hi

    refs = defaultdict(set)
    for cls, e in slots.items():
        for _s, a, _n in e:
            if a < tail_start:
                refs[a].add(cls)

    unique = {a: next(iter(s)) for a, s in refs.items() if len(s) == 1}
    shared = {a: s for a, s in refs.items() if len(s) > 1}

    seeds = defaultdict(list)
    for a, c in unique.items():
        seeds[c].append(a)
    for c in seeds:
        seeds[c].sort()

    assigned = dict(unique)
    unresolved = []
    for a, cands in sorted(shared.items()):
        best, bestd = None, None
        for c in cands:
            for s in seeds.get(c, ()):
                dist = abs(s - a)
                if bestd is None or dist < bestd:
                    best, bestd = c, dist
        if best is None:
            unresolved.append(a)
        else:
            assigned[a] = best

    owned = defaultdict(set)
    for a, c in assigned.items():
        owned[c].add(a)

    def to_offset(addr):
        for s in secs:
            if (s["flags"] & SHF_ALLOC and s["type"] != SHT_NOBITS
                    and s["size"] and s["addr"] <= addr
                    < s["addr"] + s["size"]):
                return s["offset"] + (addr - s["addr"])
        return None

    if args.clusters:
        print("=== class ranges in the anonymous .text blob ===")
        print(f"blob is {lo:#x}..{tail_start:#x}; the linkonce tail above "
              f"that is\nalready per-function and needs no splitting.\n")
        print(f"  {len(unique)} address(es) owned by exactly one class")
        print(f"  {len(shared)} shared (inherited) -- assigned by proximity")
        if unresolved:
            print(f"  {len(unresolved)} unassignable")
        print()
        rows = sorted((min(v), max(v), len(v), c)
                      for c, v in owned.items() if v)
        prev_end = prev_cls = None
        overlaps = 0
        for start, end, n, cls in rows:
            flag = ""
            if prev_end is not None and start < prev_end:
                flag = f"  OVERLAPS {prev_cls}"
                overlaps += 1
            print(f"  {start:#010x}..{end:#010x}  {n:>4} fn  {cls}{flag}")
            if prev_end is None or end > prev_end:
                prev_end, prev_cls = end, cls
        print(f"\n  {len(rows)} class(es), {overlaps} overlapping")
        print("  clean, ordered ranges are translation-unit candidates")
        print()

    def dense_core(addrs, gap):
        a = sorted(addrs)
        runs, cur = [], [a[0]]
        for x in a[1:]:
            if x - cur[-1] <= gap:
                cur.append(x)
            else:
                runs.append(cur)
                cur = [x]
        runs.append(cur)
        return max(runs, key=len)

    if args.yaml:
        starts = []
        if args.funcs.is_dir():
            for p in args.funcs.rglob("func_*.s"):
                m = re.match(r"^func_([0-9A-Fa-f]{8})$", p.stem)
                if m:
                    starts.append(int(m.group(1), 16))
            starts = sorted(set(starts))

        def next_start(after):
            i = bisect.bisect_right(starts, after)
            return starts[i] if i < len(starts) else None

        def count_between(a, b):
            if b is None:
                return len(starts) - bisect.bisect_left(starts, a)
            return bisect.bisect_left(starts, b) - bisect.bisect_left(starts, a)

        print("=== splat subsegments ===")
        if not starts:
            print(f"# WARNING: no func_*.s under {args.funcs} -- cannot tell")
            print("# where a class's code ends, so no unk_ rows are emitted")
            print("# and every gap will be absorbed by the class above it.")
            print("# Run configure.py --split first.")
        print("#")
        print("# ClassName rows are bounded by vtable evidence.")
        print("# unk_XXXXXXXX rows are everything between one class's last")
        print("# known function and the next class -- unattributed code that")
        print("# no vtable points at. Renaming one is a claim; make it only")
        print("# when you know what is in there.")
        print()

        cores = {}
        for cls, v in owned.items():
            if not v:
                continue
            c = dense_core(v, args.gap)
            cores[cls] = (c[0], c[-1], len(c), len(v) - len(c))

        rows = sorted((s, e, n, out, c) for c, (s, e, n, out) in cores.items())
        kept, dropped = [], []
        last_end = None
        for s, e, n, out, cls in rows:
            if last_end is not None and s < last_end:
                dropped.append((s, e, n, cls))
                continue
            kept.append((s, e, n, out, cls))
            last_end = e

        bounds = []
        for i, (s, e, n, out, cls) in enumerate(kept):
            nxt = kept[i + 1][0] if i + 1 < len(kept) else None
            bounds.append([s, cls, n, out])
            gap = next_start(e) if starts else None
            if gap is not None and (nxt is None or gap < nxt):
                bounds.append([gap, f"unk_{gap:08X}", None, None])

        n_unk = n_unk_fn = 0
        for j, (addr, name, known, stray) in enumerate(bounds):
            nxt = bounds[j + 1][0] if j + 1 < len(bounds) else None
            total = count_between(addr, nxt) if starts else None
            off = to_offset(addr)
            note = f"{addr:#010x}"
            if total is not None:
                note += f", {total} fn"
            if known is not None and total is not None and total != known:
                note += f" ({known} attributed)"
            elif known is not None:
                note += f" ({known} attributed)"
            if stray:
                note += f", {stray} stray"
            if known is None:
                n_unk += 1
                n_unk_fn += total or 0
            if off is None:
                print(f"#     [???, cpp, {name}]   # {note}  UNMAPPED")
            else:
                print(f"      - [{off:#x}, cpp, {name}]   # {note}")

        print(f"\n# {len(bounds)} subsegment(s): "
              f"{len(bounds) - n_unk} class, {n_unk} unattributed")
        if starts:
            print(f"# {n_unk_fn} of {len(starts)} function(s) "
                  f"({100.0 * n_unk_fn / len(starts):.0f}%) are in unk_ rows")
        if dropped:
            print(f"# {len(dropped)} class(es) dropped, still overlapping "
                  f"after coring:")
            for s, e, n, cls in dropped:
                print(f"#     {s:#010x}..{e:#010x}  {n:>3} fn  {cls}")
        print()

    if args.unknown:
        print("=== unnamed vtable targets ===")
        print("functions in the anonymous .text blob that a vtable "
              "points at\n")
        for cls, slot, addr in sorted(unknown, key=lambda x: x[2]):
            p = proposals.get(addr)
            note = f"  proposed {show(p[0])}" if p else ""
            print(f"  {addr:#010x}  {cls}[{slot}]{note}")
        print()

    if args.classes:
        print("=== classes ===")
        members = defaultdict(list)
        for addr, nm in funcs.items():
            p = split_member(nm)
            if p:
                members[p[1]].append((addr, nm))
        for cls in sorted(set(members) | set(vtables)):
            vt = vtables.get(cls)
            extra = (f"   vtable {vt[0]:#010x}, {len(slots.get(cls, []))} "
                     f"virtual(s)") if vt else ""
            print(f"\n  {cls}{extra}")
            for addr, nm in sorted(members.get(cls, [])):
                print(f"      {addr:#010x}  {show(nm)}")
        print()

    if args.vtables:
        print("=== vtables ===")
        for cls, e in sorted(slots.items()):
            print(f"\n  {cls}  @ {vtables[cls][0]:#010x}  "
                  f"{len(e)} virtual(s)")
            for slot, addr, nm in e:
                if nm:
                    print(f"      [{slot:>3}] {addr:#010x}  {show(nm)}")
                else:
                    p = proposals.get(addr)
                    print(f"      [{slot:>3}] {addr:#010x}  func_{addr:08X}"
                          + (f"  ?? {show(p[0])}" if p else ""))
        print()

    if args.write_symbols:
        path = args.symbols_path
        existing, lines = set(), []
        if path.is_file():
            for line in path.read_text().splitlines():
                lines.append(line)
                st = line.strip()
                if st and not st.startswith("//"):
                    existing.add(st.split("=", 1)[0].strip())
        added = []
        for addr, nm in sorted(funcs.items()):
            if nm not in existing:
                added.append(f"{nm} = {addr:#010x}; // type:func")
                existing.add(nm)
        for addr, (nm, cls, slot) in sorted(proposals.items()):
            if nm not in existing:
                added.append(f"{nm} = {addr:#010x}; // type:func "
                             f"PROPOSED {cls} vtable slot {slot}")
                existing.add(nm)
        if not added:
            print("symbol_addrs.txt already has everything")
            return 0
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["// --- tools/linkonce.py ---",
                  "// PROPOSED names are inferred from vtable layout, not "
                  "read from the",
                  "// binary. Verify before relying on them."] + added
        path.write_text("\n".join(lines).rstrip("\n") + "\n")
        print(f"{path}: +{len(added)} symbol(s)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
