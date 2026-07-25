#!/usr/bin/env python3
import argparse
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
LINKED = ROOT / "build" / "linked.elf"
SRC = ROOT / "src"
README = ROOT / "README.md"

SHT_SYMTAB = 2
STT_FUNC = 2

START = "<!-- progress:start -->"
END = "<!-- progress:end -->"

C_FUNC_RE = re.compile(
    r"^(?:static\s+)?[^\s]+\s+([^\s(]+)\(([^;)]*)\)[^;]+?{", re.MULTILINE)
C_COMMENT_RE = re.compile(
    r"//.*?$|/\*.*?\*/|'(?:\\.|[^\\'])*'|\"(?:\\.|[^\\\"])*\"",
    re.DOTALL | re.MULTILINE)

def strip_comments(text):
    return C_COMMENT_RE.sub(
        lambda m: " " if m.group(0).startswith("/") else m.group(0), text)

def elf_functions(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")
    shoff = struct.unpack_from("<I", d, 0x20)[0]
    shentsize, shnum = struct.unpack_from("<HH", d, 0x2E)

    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        nm, st, fl, ad, off, sz, lk, inf, al, ent = struct.unpack_from(
            "<10I", d, o)
        secs.append(dict(type=st, offset=off, size=sz, link=lk, entsize=ent))

    out = {}
    for s in secs:
        if s["type"] != SHT_SYMTAB:
            continue
        strtab = secs[s["link"]]
        n = s["size"] // (s["entsize"] or 16)
        for i in range(n):
            o = s["offset"] + i * (s["entsize"] or 16)
            name_off, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", d, o)
            if (info & 0xF) != STT_FUNC or not size:
                continue
            e = d.index(b"\0", strtab["offset"] + name_off)
            name = d[strtab["offset"] + name_off:e].decode(errors="replace")
            if name:
                out[name] = size
    return out

def c_definitions():
    out = {}
    if not SRC.is_dir():
        return out
    for p in sorted(SRC.rglob("*.c")) + sorted(SRC.rglob("*.cpp")):
        text = strip_comments(p.read_text(encoding="utf-8", errors="replace"))
        names = {m.group(1) for m in C_FUNC_RE.finditer(text)}
        if names:
            out[p.relative_to(ROOT).as_posix()] = names
    return out

def collect():
    if not LINKED.is_file():
        sys.exit(f"{LINKED} missing -- run `ninja` first")
    funcs = elf_functions(LINKED)
    defs = c_definitions()

    total = sum(funcs.values())
    per_file = []
    done_names = set()
    for f, names in sorted(defs.items()):
        known = {n for n in names if n in funcs}
        done_names |= known
        per_file.append((f, len(known), sum(funcs[n] for n in known)))

    done = sum(funcs[n] for n in done_names)
    unmatched = {n for names in defs.values() for n in names} - set(funcs)
    return funcs, per_file, done, total, unmatched

def render(per_file, done, total):
    pct = 100.0 * done / total if total else 0.0
    lines = [
        f"**{pct:.4f}%** of the code is decompiled "
        f"({done:,} / {total:,} bytes).",
        "",
        "| File | Functions | Bytes |",
        "|---|---:|---:|",
    ]
    for f, n, b in per_file:
        if n:
            lines.append(f"| `{f}` | {n} | {b:,} |")
    if not any(n for _, n, _ in per_file):
        lines.append("| _nothing yet_ | 0 | 0 |")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", action="store_true",
                    help=f"rewrite the block between {START} and {END}")
    ap.add_argument("--json", metavar="PATH",
                    help="write a shields.io endpoint json")
    args = ap.parse_args()

    funcs, per_file, done, total, unmatched = collect()
    pct = 100.0 * done / total if total else 0.0

    print(f"{pct:.4f}%  {done:,} / {total:,} bytes  "
          f"({len(funcs):,} functions total)")
    for f, n, b in per_file:
        if n:
            print(f"  {f:<24} {n:>5} func  {b:>9,} bytes")
    if unmatched:
        print(f"\nwarning: {len(unmatched)} C definition(s) with no sized "
              f"symbol in the build:", file=sys.stderr)
        for n in sorted(unmatched)[:10]:
            print(f"  {n}", file=sys.stderr)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "schemaVersion": 1,
            "label": "decompiled",
            "message": f"{pct:.4f}%",
            "color": "brightgreen" if pct > 50 else
                     "yellow" if pct > 10 else "red",
        }) + "\n")
        print(f"wrote {args.json}")

    if args.readme:
        text = README.read_text(encoding="utf-8")
        if START not in text or END not in text:
            sys.exit(f"README.md has no {START} / {END} block")
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        README.write_text(
            f"{head}{START}\n{render(per_file, done, total)}\n{END}{tail}",
            encoding="utf-8")
        print(f"updated {README}")

if __name__ == "__main__":
    main()
