#!/usr/bin/env python3
import hashlib
import struct
import sys
from pathlib import Path

PT_LOAD = 1
SHT_NOBITS = 8
SHF_EXECINSTR = 0x4
SHF_WRITE = 0x1
EXACT_SEGMENT_END = True

TEXT_SUBSEGMENT_TYPE = "c"

def read_elf(path: Path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        sys.exit(f"{path}: not an ELF")
    if d[4] != 1 or d[5] != 1:
        sys.exit(f"{path}: expected ELF32 little-endian")

    e_entry, e_phoff, e_shoff = struct.unpack_from("<III", d, 0x18)
    e_phentsize, e_phnum = struct.unpack_from("<HH", d, 0x2A)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", d, 0x2E)

    loads = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", d, o)
        if t == PT_LOAD and fsz:
            loads.append(dict(offset=off, vaddr=va, filesz=fsz,
                              memsz=msz, flags=fl))
    loads.sort(key=lambda p: p["offset"])

    secs = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        (nm, st, fl, ad, off, sz, lk, inf, al, ent) = struct.unpack_from(
            "<10I", d, o)
        secs.append(dict(name_off=nm, type=st, flags=fl, addr=ad,
                         offset=off, size=sz))
    base = secs[e_shstrndx]["offset"]
    for s in secs:
        e = d.index(b"\0", base + s["name_off"])
        s["name"] = d[base + s["name_off"]:e].decode()

    return d, e_entry, loads, secs

def classify(s):
    if s["type"] == SHT_NOBITS:
        return "bss"
    if s["flags"] & SHF_EXECINSTR:
        return "text"
    if s["flags"] & SHF_WRITE:
        return "data"
    return "rodata"

def merge(sections):
    out = []
    for s in sections:
        if out:
            prev = out[-1]
            gap = s["offset"] - (prev["offset"] + prev["size"])
            if prev["kind"] == s["kind"] and 0 <= gap < 0x20:
                prev["size"] = s["offset"] + s["size"] - prev["offset"]
                prev["members"].append(s["name"])
                continue
        out.append(dict(kind=s["kind"], offset=s["offset"], size=s["size"],
                        addr=s["addr"], name=s["name"], members=[s["name"]]))
    return out

def subseg_name(block, index):
    n = block["name"].lstrip(".")
    if len(block["members"]) > 1:
        n = f"{block['kind']}_{index}"
    for ch in "$@ ?*<>|":
        n = n.replace(ch, "_")
    return n.replace(".", "_")

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: gen_splat_yaml.py <path/to/SLES_XXX.XX>")

    path = Path(sys.argv[1])
    d, entry, loads, secs = read_elf(path)
    sha1 = hashlib.sha1(d).hexdigest()
    name = path.name
    base = name.replace(".", "_")

    if not loads:
        sys.exit("no PT_LOAD segments found")

    alloc = [s for s in secs if s["addr"] and s["size"] and s["type"] != 0]
    for s in alloc:
        s["kind"] = classify(s)

    loaded = sorted((s for s in alloc if s["type"] != SHT_NOBITS),
                    key=lambda s: s["offset"])
    bss = sorted((s for s in alloc if s["type"] == SHT_NOBITS),
                 key=lambda s: s["addr"])
    blocks = merge(loaded)

    bss_total = 0
    if bss:
        bss_total = (max(s["addr"] + s["size"] for s in bss)
                     - bss[0]["addr"])

    log = lambda m: print(m, file=sys.stderr)
    log(f"# {name}")
    log(f"# entry 0x{entry:08X}  sha1 {sha1}")
    log(f"# {len(loaded)} loaded sections -> {len(blocks)} blocks "
        f"across {len(loads)} PT_LOAD")

    for p in loads:
        p["blocks"] = [b for b in blocks
                       if p["offset"] <= b["offset"] < p["offset"] + p["filesz"]]

    orphans = [b for b in blocks if not any(b in p["blocks"] for p in loads)]
    if orphans:
        log("# WARNING: blocks outside every PT_LOAD (not emitted):")
        for b in orphans:
            log(f"#   {b['name']} off 0x{b['offset']:X} size 0x{b['size']:X}")

    lines = [f"sha1: {sha1}", "", "options:",
             f"  basename: {base}",
             f"  target_path: orig/{name}",
             "  platform: ps2",
             "  compiler: GCC",
             "  base_path: ..",
             "  asm_path: asm",
             "  src_path: src",
             "  build_path: build",
             "  asset_path: assets",
             "  create_undefined_funcs_auto: True",
             "  create_undefined_syms_auto: True",
             "  symbol_addrs_path: config/symbol_addrs.txt",
             "  undefined_funcs_auto_path: config/undefined_funcs_auto.txt",
             "  undefined_syms_auto_path: config/undefined_syms_auto.txt",
             "  ld_script_path: config/generated.ld",
             "  find_file_boundaries: True",
             '  section_order: [".text", ".data", ".rodata", ".bss"]',
             '  auto_link_sections: [".data", ".rodata", ".bss"]',
             "  ld_align_section_vram_end: False",
             "  ld_align_segment_vram_end: False",
             "  auto_decompile_empty_functions: False",
             "", "segments:"]

    for i, p in enumerate(loads):
        last = i == len(loads) - 1
        blks = p["blocks"]
        if not blks:
            continue

        kinds = {b["kind"] for b in blks}
        mixed = "data" in kinds and "rodata" in kinds

        end = p["offset"] + p["filesz"]
        tail = None
        if end % 4:
            if EXACT_SEGMENT_END:
                tail = end & ~3
            else:
                end = (end + 3) & ~3

        flags = ("R" if p["flags"] & 4 else "-") + \
                ("W" if p["flags"] & 2 else "-") + \
                ("X" if p["flags"] & 1 else "-")
        log(f"#")
        log(f"# PT_LOAD[{i}] {flags}  vram 0x{p['vaddr']:08X}  "
            f"file 0x{p['offset']:X}..0x{end:X}"
            f"{'  (mixed data/rodata -> all data)' if mixed else ''}")

        seg = f"{base}_{i}"
        lines += [f"  - name: {seg}",
                  "    type: code",
                  f"    start: 0x{p['offset']:X}",
                  f"    vram: 0x{p['vaddr']:08X}",
                  "    subalign: 4"]
        if last and bss_total:
            lines.append(f"    bss_size: 0x{bss_total:X}")
        lines.append("    subsegments:")

        for j, b in enumerate(blks):
            if b["kind"] == "text":
                kind = TEXT_SUBSEGMENT_TYPE
            elif mixed:
                kind = "data"
            else:
                kind = b["kind"]
            log(f"#   {kind:<7} vram 0x{b['addr']:08X} off 0x{b['offset']:06X} "
                f"size 0x{b['size']:X}"
                + (f"  ({len(b['members'])} merged)"
                   if len(b["members"]) > 1 else ""))
            lines.append(
                f"      - [0x{b['offset']:X}, {kind}, {subseg_name(b, j)}]")

        if tail is not None:
            nm = f"{subseg_name(blks[-1], len(blks) - 1)}_tail"
            log(f"#   bin     off 0x{tail:06X} size 0x{end - tail:X}"
                f"  (trailing partial word)")
            lines.append(f"      - [0x{tail:X}, bin, {nm}]")

        lines.append(f"      - [0x{end:X}]")
        lines.append(f"  - [0x{end:X}]")

    if bss:
        log(f"#\n# bss vram 0x{bss[0]['addr']:08X}"
            f"..0x{bss[0]['addr'] + bss_total:08X} size 0x{bss_total:X}")
    if any(s["name"] in (".stab", ".stabstr") for s in secs):
        log("#\n# .stab present -- recover symbols with ccc")
    if any("_vt$" in s["name"] for s in secs):
        log("#\n# C++ binary, GNU v2 (gcc 2.x) mangling")

    out = Path("config") / f"splat.{name}.yaml"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    log(f"\nwrote {out}")

if __name__ == "__main__":
    main()
