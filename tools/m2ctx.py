#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER_ID = os.environ.get("COMPILER_ID", "ee-gcc2.96")

INCLUDES = ["-Iinclude", "-Iinclude/sdk"]
DEFINES = ["-D__GNUC__=2", "-DM2CTX"]

EXTERN_C = re.compile(r'extern\s*"C"\s*')

def strip_extern_c(text):
    out, i, n = [], 0, len(text)
    while True:
        m = EXTERN_C.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        j = m.end()
        if j < n and text[j] == "{":
            depth, k = 0, j
            while k < n:
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            out.append(text[j + 1:k])
            i = min(k + 1, n)
        else:
            i = j

STRIP = [
    (re.compile(r"__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)"), ""),
    (re.compile(r"\b__extension__\b"), ""),
    (re.compile(r"\b__restrict\b"), ""),
    (re.compile(r"\b__inline__\b"), ""),
]

def find_cpp():
    base = ROOT / "tools" / "compilers" / COMPILER_ID
    if base.is_dir():
        for pat in ("ee-cpp", "cpp.exe"):
            hits = sorted(base.rglob(pat))
            if hits:
                return hits[0]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "build" / "ctx.c")
    ap.add_argument("--keep-attributes", action="store_true",
                    help="do not strip __attribute__ etc")
    args = ap.parse_args()

    src = args.source
    if not src.is_absolute():
        src = ROOT / src
    if not src.is_file():
        sys.exit(f"{src}: not found")

    cpp = find_cpp()
    if cpp is None:
        sys.exit(f"no cpp under tools/compilers/{COMPILER_ID} -- "
                 f"run: bash tools/setup.sh {COMPILER_ID}")

    launcher = [str(ROOT / "tools" / "wibo")] if cpp.suffix == ".exe" else []
    cmd = launcher + [str(cpp), "-lang-c"] + DEFINES + INCLUDES + [
        str(src.relative_to(ROOT) if src.is_relative_to(ROOT) else src)]

    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit(f"cpp failed ({r.returncode})")

    text = strip_extern_c(r.stdout)
    if not args.keep_attributes:
        for pat, rep in STRIP:
            text = pat.sub(rep, text)

    text = "\n".join(l for l in text.splitlines()
                     if not l.startswith("# ") and not l.startswith("#line"))

    leftover = [i + 1 for i, l in enumerate(text.splitlines())
                if 'extern "C"' in l]
    if leftover:
        print(f"warning: {len(leftover)} extern \"C\" line(s) survived at "
              f"{args.out} line(s) {leftover[:5]} -- m2c will refuse to "
              f"parse this. Report it; the stripper needs widening.",
              file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"wrote {args.out}  ({len(text.splitlines())} lines)")
    print(f"\n  python3 tools/m2c/m2c.py --target mipsel-gcc-c \\")
    print(f"      --context {args.out.relative_to(ROOT)} \\")
    print(f"      asm/nonmatchings/<unit>/func_XXXXXXXX.s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
