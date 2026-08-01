#!/usr/bin/env python3
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OBJDUMPS = [
    os.environ.get("OBJDUMP", ""),
    "mips64r5900el-ps2-elf-objdump",
    "mips-linux-gnu-objdump",
    "objdump",
]

FUNC_START = re.compile(r"^[0-9a-fA-F]+\s+<(?P<name>[^>]+)>:\s*$")
INSN = re.compile(r"^\s*(?P<addr>[0-9a-fA-F]+):\s+(?P<body>.*?)\s*$")

def find_objdump(explicit):
    for cand in ([explicit] if explicit else []) + OBJDUMPS:
        if cand and shutil.which(cand):
            return cand
    sys.exit("no objdump found -- pass --objdump or set $OBJDUMP")

def disassemble(objdump, path, want, keep_targets=False):
    try:
        r = subprocess.run(
            [objdump, "-d", "--no-show-raw-insn", str(path)],
            capture_output=True, text=True, timeout=120)
    except OSError as e:
        sys.exit(f"{objdump}: {e}")
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit(f"{objdump} failed on {path}")

    out, inside = [], False
    for line in r.stdout.splitlines():
        m = FUNC_START.match(line)
        if m:
            inside = m.group("name") == want
            continue
        if not inside:
            continue
        if not line.strip():
            inside = False
            continue
        m = INSN.match(line)
        if not m:
            continue
        body = m.group("body")
        body = re.sub(r"[0-9a-fA-F]+\s+<([^>+]+)(?:\+0x[0-9a-fA-F]+)?>",
                      r"<\1>" if not keep_targets else r"<\1+..>", body)
        body = re.sub(r"\s+", " ", body).strip()
        out.append(body)
    return out

def units(root):
    cfg = root / "objdiff.json"
    if not cfg.is_file():
        sys.exit("objdiff.json missing -- run configure.py first")
    data = json.loads(cfg.read_text())
    return {u["name"]: (root / u["target_path"], root / u["base_path"])
            for u in data.get("units", [])}

def columns(a, b, width, context):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            span = [(" ", a[i], b[j]) for i, j in zip(range(i1, i2),
                                                      range(j1, j2))]
            if context is not None and len(span) > 2 * context:
                rows += span[:context]
                rows.append(("~", f"... {len(span) - 2 * context} identical",
                             ""))
                rows += span[-context:]
            else:
                rows += span
        elif tag == "replace":
            n = max(i2 - i1, j2 - j1)
            for k in range(n):
                left = a[i1 + k] if i1 + k < i2 else ""
                right = b[j1 + k] if j1 + k < j2 else ""
                rows.append(("|", left, right))
        elif tag == "delete":
            for i in range(i1, i2):
                rows.append(("-", a[i], ""))
        elif tag == "insert":
            for j in range(j1, j2):
                rows.append(("+", "", b[j]))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unit")
    ap.add_argument("function")
    ap.add_argument("--objdump", default=None)
    ap.add_argument("--context", type=int, default=3,
                    help="identical instructions to keep around a change "
                         "(default 3, use -1 for all)")
    ap.add_argument("--branch-targets", action="store_true",
                    help="keep numeric branch offsets (noisy once sizes differ)")
    ap.add_argument("--unified", action="store_true",
                    help="plain unified diff instead of columns")
    args = ap.parse_args()

    objdump = find_objdump(args.objdump)
    table = units(ROOT)
    if args.unit not in table:
        sys.exit(f"unknown unit {args.unit} -- "
                 f"try one of: {', '.join(sorted(table)[:8])} ...")
    tpath, bpath = table[args.unit]
    for p in (tpath, bpath):
        if not p.is_file():
            sys.exit(f"{p}: not built -- run ninja first")

    tgt = disassemble(objdump, tpath, args.function,
                      args.branch_targets)
    got = disassemble(objdump, bpath, args.function,
                      args.branch_targets)

    if not tgt:
        sys.exit(f"{args.function} not found in {tpath}")
    if not got:
        sys.exit(f"{args.function} not found in {bpath} "
                 f"(mangled? run unitdiff)")

    print(f"{args.function}  in  {args.unit}")
    print(f"  target {len(tgt)} instruction(s), {len(tgt) * 4:#x} bytes")
    print(f"  built  {len(got)} instruction(s), {len(got) * 4:#x} bytes"
          f"  ({(len(got) - len(tgt)) * 4:+d})")
    print()

    if tgt == got:
        print("  identical")
        return 0

    if args.unified:
        for line in difflib.unified_diff(tgt, got, "target", "built",
                                         lineterm="", n=max(args.context, 0)):
            print(line)
        return 1

    ctx = None if args.context < 0 else args.context
    rows = columns(tgt, got, 0, ctx)
    w = max((len(l) for _, l, _ in rows), default=0)
    w = min(max(w, 20), 52)
    for mark, left, right in rows:
        if mark == "~":
            print(f"      {left}")
        else:
            print(f"  {mark} {left:<{w}}  {right}")
    print()

    ins = sum(1 for m, _, _ in rows if m == "+")
    dele = sum(1 for m, _, _ in rows if m == "-")
    repl = sum(1 for m, _, _ in rows if m == "|")
    print(f"  {dele} missing, {ins} extra, {repl} changed")
    return 1

if __name__ == "__main__":
    sys.exit(main())
