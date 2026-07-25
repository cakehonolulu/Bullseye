#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ONE_LINE = re.compile(
    r"^\s(\.\S+)\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(\S+)\s*$")
NAME_ONLY = re.compile(r"^\s(\.\S+)\s*$")
ADDR_ONLY = re.compile(
    r"^\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(\S+)\s*$")

def parse(path):
    entries = []
    pending = None
    for line in path.read_text(errors="replace").splitlines():
        m = ONE_LINE.match(line)
        if m:
            name, addr, size, obj = m.groups()
            entries.append((int(addr, 16), int(size, 16), name, obj))
            pending = None
            continue
        m = NAME_ONLY.match(line)
        if m:
            pending = m.group(1)
            continue
        m = ADDR_ONLY.match(line)
        if m and pending:
            addr, size, obj = m.groups()
            entries.append((int(addr, 16), int(size, 16), pending, obj))
            pending = None
            continue
        pending = None
    return entries

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: mapgap.py <map file>")
    path = Path(sys.argv[1])
    entries = [e for e in parse(path) if e[0] != 0 and e[1] != 0]
    entries.sort(key=lambda e: e[0])

    if not entries:
        sys.exit("no placed input sections found -- is this a linker map?")

    print(f"{len(entries)} placed input sections, "
          f"{entries[0][0]:#010x}..{entries[-1][0] + entries[-1][1]:#010x}\n")

    prev_end = None
    prev = None
    gaps = 0
    for addr, size, name, obj in entries:
        if prev_end is not None and addr != prev_end:
            delta = addr - prev_end
            gaps += 1
            kind = "GAP " if delta > 0 else "OVERLAP"
            print(f"{kind} {delta:+#x} at {prev_end:#010x} -> {addr:#010x}")
            print(f"     after  {prev[2]:<24} {prev[1]:#8x}  {prev[3]}")
            print(f"     before {name:<24} {size:#8x}  {obj}")
            for a in (4, 8, 16, 32, 64, 128, 256):
                if addr % a == 0 and prev_end % a != 0:
                    print(f"     consistent with ALIGN({a})")
                    break
            print()
        prev_end = addr + size
        prev = (addr, size, name, obj)

    if gaps == 0:
        print("no gaps -- every section starts where the previous one ended")
    else:
        print(f"{gaps} gap(s). The first one is the one to fix; "
              f"later gaps are often downstream of it.")

if __name__ == "__main__":
    main()
