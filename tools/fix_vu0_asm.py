#!/usr/bin/env python3
import re
import sys
from pathlib import Path

INSN = re.compile(r'(?P<mnem>\bv[a-z]+(?:\.[a-z]+)?)\s+'
                  r'(?P<operands>[^\n#]+?)\s*(?P<comment>#.*)?$')
SPECIAL_NOSUF = {"Q", "R", "I"}
SPECIAL_VEC = {"ACC"}
BARE_VF = re.compile(r'^\$?vf(\d+)([xyzw]?)$')

def split_operands(s):
    return [p.strip() for p in s.split(',')]

def fix_operand(tok, suf):
    bare = tok[1:] if tok.startswith('$') else tok
    if bare in SPECIAL_NOSUF:
        return '$' + bare
    if bare in SPECIAL_VEC:
        return '$' + bare + (suf or '')
    m = BARE_VF.match(tok)
    if m:
        num, letter = m.groups()
        if letter:
            return f'$vf{num}{letter}'
        return f'$vf{num}{suf or ""}'
    return tok

def fix_line(line):
    stripped = line.rstrip('\n')
    m = INSN.search(stripped)
    if not m:
        return line, False
    mnem = m.group('mnem')
    if mnem in ('vnop', 'vwaitq', 'vcallms'):
        return line, False

    base, _, dotsuf = mnem.partition('.')
    suf = dotsuf if dotsuf else None

    operands = split_operands(m.group('operands'))
    new_operands = [fix_operand(o, suf) for o in operands]
    if new_operands == operands:
        return line, False

    prefix = stripped[:m.start('mnem')]
    out = f"{prefix}{mnem} {','.join(new_operands)}"
    comment = m.group('comment')
    if comment:
        out += f" {comment}"
    return out + "\n", True

def process(path: Path, check: bool):
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    changed = 0
    out_lines = []
    for line in lines:
        new_line, did = fix_line(line)
        out_lines.append(new_line)
        changed += did
    if changed and not check:
        path.write_text("".join(out_lines))
    return changed

def collect(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            yield from sorted(p.rglob("*.s"))
        elif p.suffix == ".s":
            yield p

def main():
    argv = sys.argv[1:]
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    if not argv:
        sys.exit("usage: fix_vu0_asm.py [--check] <file-or-dir> ...")

    total_files = 0
    total_lines = 0
    for f in collect(argv):
        n = process(f, check)
        if n:
            total_files += 1
            total_lines += n

    print(f"\n{total_lines} line(s) across {total_files} file(s)"
          f"{' (dry run, nothing written)' if check else ''}")

if __name__ == "__main__":
    main()
