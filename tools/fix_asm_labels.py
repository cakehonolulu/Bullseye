#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

OPEN_RE = re.compile(r"^\s*(glabel|dlabel|alabel)\s+(\S+?)\s*(?:,|$)")
CLOSE_RE = re.compile(r"^\s*(endlabel|enddlabel)\s+(\S+?)\s*(?:,|$)")

WANT = {"glabel": "endlabel"}

def inspect(path: Path):
    lines = path.read_text(errors="replace").splitlines(keepends=True)
    opens, closes = [], []
    for i, ln in enumerate(lines):
        m = OPEN_RE.match(ln)
        if m:
            opens.append((i, m.group(1), m.group(2)))
            continue
        m = CLOSE_RE.match(ln)
        if m:
            closes.append((i, m.group(1), m.group(2)))
    return lines, opens, closes

def fix(path: Path, check: bool):
    lines, opens, closes = inspect(path)
    if not opens:
        return 0, []

    problems = []
    fixed = 0

    by_symbol = {}
    for i, macro, sym in closes:
        by_symbol.setdefault(sym, []).append((i, macro))

    for _, macro, sym in opens:
        want = WANT.get(macro)
        if want is None:
            continue
        entries = by_symbol.get(sym)
        if not entries:
            problems.append(f"{path.name}: {macro} {sym} has no terminator")
            continue
        for idx, (i, have) in enumerate(entries):
            if have == want:
                continue
            lines[i] = lines[i].replace(have, want, 1)
            entries[idx] = (i, want)
            fixed += 1

    opened = {sym for _, _, sym in opens}
    for i, macro, sym in closes:
        if sym not in opened:
            problems.append(
                f"{path.name}:{i + 1}: {macro} {sym} closes a symbol this "
                f"file never opened -- .size will be wrong")

    if fixed and not check:
        path.write_text("".join(lines))
    return fixed, problems

def collect(paths):
    for name in paths:
        p = Path(name)
        if p.is_dir():
            yield from sorted(p.rglob("*.s"))
        elif p.suffix == ".s":
            yield p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["asm"],
                    help="files or directories to scan (default: asm)")
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    ap.add_argument("--quiet", action="store_true",
                    help="only print the summary")
    args = ap.parse_args()

    total_files = 0
    total_fixed = 0
    all_problems = []

    for f in collect(args.paths):
        n, problems = fix(f, args.check)
        all_problems += problems
        if n:
            total_files += 1
            total_fixed += n
            #if not args.quiet:
                #print(f"{f}: {n} terminator(s) corrected")

    if all_problems:
        print(f"\n{len(all_problems)} unresolved problem(s):",
              file=sys.stderr)
        for p in all_problems:
            print(f"  {p}", file=sys.stderr)

    print(f"\n{total_fixed} terminator(s) across {total_files} file(s)"
          f"{' (dry run, nothing written)' if args.check else ''}")

    return 1 if (args.check and all_problems) else 0

if __name__ == "__main__":
    sys.exit(main())
