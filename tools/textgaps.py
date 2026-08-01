#!/usr/bin/env python3
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

WORD_RE = re.compile(
    r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s*\*/")
NAME_RE = re.compile(r"^func_([0-9A-Fa-f]{8})\.s$")

def scan(path: Path):
    out = []
    bad = []
    for p in sorted(path.iterdir()):
        m = NAME_RE.match(p.name)
        if not m:
            continue
        start = int(m.group(1), 16)
        last_va = None
        last_word = None
        for wm in WORD_RE.finditer(p.read_text(errors="replace")):
            va = int(wm.group(1), 16)
            if last_va is None or va > last_va:
                last_va = va
                last_word = wm.group(2)
        if last_va is None:
            bad.append(p.name)
            continue
        out.append((start, last_va + 4, p.stem, last_word))
    out.sort()
    return out, bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path, help="asm/nonmatchings/<unit>")
    ap.add_argument("--list", action="store_true",
                    help="print every gap, not just the histogram")
    ap.add_argument("--yaml", action="store_true",
                    help="emit splat subsegment rows for each boundary")
    ap.add_argument("--min", type=int, default=0,
                    help="only report gaps of at least this many bytes")
    ap.add_argument("--file-offset", type=lambda s: int(s, 0), default=None,
                    help="vram - file offset, for --yaml (e.g. 0x100000-0x1000)")
    args = ap.parse_args()

    if not args.dir.is_dir():
        sys.exit(f"{args.dir}: not a directory")

    funcs, bad = scan(args.dir)
    if not funcs:
        sys.exit(f"no parseable func_*.s under {args.dir}")
    if bad:
        print(f"warning: {len(bad)} file(s) had no /* vram word */ column, "
              f"skipped (e.g. {bad[0]})\n", file=sys.stderr)

    lo, hi = funcs[0][0], funcs[-1][1]
    print(f"{len(funcs)} functions, {lo:#010x}..{hi:#010x}")

    gaps = []
    overlaps = []
    for (s0, e0, n0, w0), (s1, _, n1, _) in zip(funcs, funcs[1:]):
        d = s1 - e0
        if d > 0:
            gaps.append((e0, d, n0, n1, w0))
        elif d < 0:
            overlaps.append((e0, d, n0, n1))

    if overlaps:
        print(f"\n{len(overlaps)} OVERLAP(s) -- the disassembly disagrees "
              f"with itself, look at these first:")
        for e0, d, n0, n1 in overlaps[:10]:
            print(f"  {e0:#010x} {d:+d}  {n0} -> {n1}")

    kept = [g for g in gaps if g[1] >= args.min]
    print(f"\n{len(gaps)} gap(s) between {len(funcs) - 1} adjacent pairs "
          f"({100.0 * len(gaps) / max(len(funcs) - 1, 1):.1f}% of boundaries)")
    print(f"{sum(g[1] for g in gaps)} padding byte(s) total")

    print("\ngap size:")
    for size, count in sorted(Counter(g[1] for g in gaps).items()):
        print(f"  {size:>5} bytes   {count:>6}")

    print("\nsmallest alignment that explains the gap:")
    expl = Counter()
    for end, d, _, _, _ in gaps:
        start = end + d
        for a in (8, 16, 32, 64, 128, 256):
            if start % a == 0 and end % a != 0 and d < a:
                expl[a] += 1
                break
        else:
            expl[0] += 1
    for a, count in sorted(expl.items()):
        label = f"ALIGN({a})" if a else "no power-of-two fits"
        print(f"  {label:<22} {count:>6}")

    print("\npadding content:")
    for word, count in Counter(
            g[4] for g in gaps).most_common(5):
        print(f"  last word before gap  {word}   {count:>6}")

    frac = len(gaps) / max(len(funcs) - 1, 1)
    print()
    if frac > 0.30:
        print("gaps are common")
    else:
        print("gaps are rare?")

    if args.list or args.yaml:
        print()
        for end, d, n0, n1, _ in kept:
            start = end + d
            if args.yaml:
                if args.file_offset is None:
                    print(f"      - [<file offset of {start:#x}>, c, "
                          f"{n1.lower()}]")
                else:
                    print(f"      - [{start - args.file_offset:#x}, c, "
                          f"{n1.lower()}]")
            else:
                print(f"  {end:#010x} +{d:<3} -> {start:#010x}   "
                      f"after {n0}  before {n1}")

if __name__ == "__main__":
    main()
