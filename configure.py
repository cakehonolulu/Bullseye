#!/usr/bin/env python3
import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
VERSION = "SLES_514.48"
USE_O_AS_SUFFIX = False

AS = "mips64r5900el-ps2-elf-as"
LD = "mips64r5900el-ps2-elf-ld"

COMPILER_ID = os.environ.get("COMPILER_ID", "ee-gcc2.96")

WIBO = ROOT / "tools" / "wibo"

CC1_FLAGS = [
    "-O2",
    "-g2",
    "-mcpu=r5900",
    "-mips3",
    "-fno-common",
    "-funsigned-char",
    "-fno-strict-aliasing",
    "-falign-functions=2",
    "-mno-check-zero-division",
    "-quiet",
    "-falign-loops=2",
    "-falign-jumps=2",
    "-mabi=eabi",
]
CC1PLUS_FLAGS = ["-fno-exceptions"]
CPP_FLAGS = ["-D__GNUC__=2"]
CPP_C_FLAGS = []
CPP_CXX_FLAGS = ["-D__cplusplus"]
INCLUDES = ["-Iinclude", "-Iinclude/sdk"]

AS_FLAGS = ["-EL", "-march=r5900", "-mabi=eabi", "-G0", "-no-pad-sections",
            "-Iinclude", "-I."]

CXX_SUFFIXES = (".cpp", ".cc", ".cxx", ".C")


def orig_header():
    path = ROOT / "orig" / VERSION
    if not path.is_file():
        return None, None
    d = path.read_bytes()
    entry, phoff = struct.unpack_from("<II", d, 0x18)
    phentsize, phnum = struct.unpack_from("<HH", d, 0x2A)

    gp = None
    for i in range(phnum):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from(
            "<8I", d, phoff + i * phentsize)
        if t == 0x70000000 and fsz >= 24:      # PT_MIPS_REGINFO
            gp = struct.unpack_from("<I", d, off + 20)[0]
    return entry, gp


def find_ld_emulation():
    try:
        out = subprocess.run([LD, "-V"], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None

    emus, seen = [], False
    for line in out.splitlines():
        if "Supported emulations" in line:
            seen = True
            emus += line.split(":", 1)[1].split()
            continue
        if seen:
            if line.startswith((" ", "\t")) and line.strip():
                emus += line.split()
            elif line.strip():
                break

    def rank(e):
        e = e.lower()
        if "n32" in e or "n64" in e:
            return 3
        if "r5900" in e:
            return 0
        if "eabi" in e:
            return 1
        return 2

    ranked = sorted(emus, key=rank)
    if ranked and rank(ranked[0]) < 2:
        return ranked[0]
    return None


def obj_path(src: Path) -> str:
    rel = src.relative_to(ROOT) if src.is_absolute() else src
    suffix = ".o" if USE_O_AS_SUFFIX else rel.suffix + ".o"
    return (Path("build") / rel).with_suffix(suffix).as_posix()


def find_compiler():
    base = ROOT / "tools" / "compilers" / COMPILER_ID
    if not base.is_dir():
        sys.exit(f"{base} missing -- run: bash tools/setup.sh {COMPILER_ID}")

    def find_one(stem):
        for pat in (stem, f"{stem}.exe"):
            hits = sorted(base.rglob(pat))
            if hits:
                return hits[0]
        return None

    cc1 = find_one("cc1")
    cc1plus = find_one("cc1plus")
    cpp = find_one("ee-cpp")

    if cc1 is None and cc1plus is None:
        sys.exit(f"no cc1 or cc1plus under {base} -- try another COMPILER_ID")

    launcher = ""
    for exe in (cc1, cc1plus, cpp):
        if exe is None:
            continue
        if exe.suffix == ".exe":
            if not WIBO.exists():
                sys.exit(f"{exe.name} is a PE binary but {WIBO} is missing -- "
                         f"re-run tools/setup.sh")
            launcher = str(WIBO)
        else:
            with exe.open("rb") as f:
                if f.read(4) != b"\x7fELF":
                    sys.exit(f"{exe} is not a native ELF binary")
            if not os.access(exe, os.X_OK):
                sys.exit(f"{exe} is not executable -- chmod +x it")

    return cc1, cc1plus, cpp, launcher


def ninja_escape(s: str) -> str:
    return s.replace("$", "$$").replace(" ", "$ ").replace(":", "$:")


def is_cxx(p: Path) -> bool:
    return p.suffix in CXX_SUFFIXES


def collect_sources():
    asm = sorted((ROOT / "asm").rglob("*.s")) if (ROOT / "asm").is_dir() else []
    asm = [p for p in asm
           if "nonmatchings" not in p.parts and "target" not in p.parts]

    src = []
    if (ROOT / "src").is_dir():
        for ext in ("*.c",) + tuple(f"*{s}" for s in CXX_SUFFIXES):
            src += sorted((ROOT / "src").rglob(ext))
    src = sorted(set(src))

    binf = sorted((ROOT / "assets").rglob("*.bin")) \
        if (ROOT / "assets").is_dir() else []
    return asm, src, binf


def unit_name(p: Path) -> str:
    return p.stem


def check_units(src):
    seen = {}
    for p in src:
        u = unit_name(p)
        if u in seen:
            sys.exit(f"unit name collision: {seen[u]} and {p} both map to "
                     f"build/target/{u}.o -- rename one")
        seen[u] = p


def write_ninja(asm, src, binf, cc1, cc1plus, cpp, launcher):
    n = []
    w = n.append
    pre = (launcher + " ") if launcher else ""
    w("# Generated by configure.py -- do not edit\n")
    w(f"cc1 = {ninja_escape(pre + str(cc1)) if cc1 else ''}")
    w(f"cc1plus = {ninja_escape(pre + str(cc1plus)) if cc1plus else ''}")
    w(f"cpp = {ninja_escape(pre + str(cpp)) if cpp else ''}")
    w(f"as = {AS}")
    w(f"ld = {LD}")
    w(f"ccflags = {' '.join(CC1_FLAGS)}")
    w(f"cxxflags = {' '.join(CC1PLUS_FLAGS)}")
    w(f"cppflags = {' '.join(CPP_FLAGS + INCLUDES)}")
    w(f"asflags = {' '.join(AS_FLAGS)}")
    w("")
    # $langflags is set per-edge below; without it here, -lang-c never
    # reaches cpp and C sources get parsed as C++.
    w("rule cpp")
    w("  command = $cpp $cppflags $langflags $in $out")
    w("  description = CPP $in")
    w("")
    w("rule cc")
    w("  command = $cc1 $ccflags $extra $in -o $out")
    w("  description = CC $in")
    w("")
    w("rule ccplus")
    w("  command = $cc1plus $ccflags $cxxflags $extra $in -o $out")
    w("  description = CXX $in")
    w("")
    w("rule as")
    w("  command = $as $asflags $extra -o $out $in")
    w("  description = AS $in")
    w("")
    entry, gp = orig_header()
    if entry:
        print(f"entry point:  {entry:#010x}")
    else:
        print("warning: could not read the entry point from "
              f"orig/{VERSION}; the ELF will not be loadable")
    if gp is not None:
        print(f"original gp:  {gp:#010x}  "
              f"(needs PT_MIPS_REGINFO -- see README)")

    emu = find_ld_emulation()
    if emu:
        print(f"ld emulation: {emu}")
    else:
        print("ld emulation: default (no r5900/eabi emulation found -- "
              "if the link reports an ABI mismatch, set it by hand)")
    w("rule bin2s")
    w("  command = python3 tools/bin2s.py $in $out")
    w("  description = BIN2S $in")
    w("")
    w("rule link")
    w(f"  command = $ld {('-m ' + emu + ' ') if emu else ''}"
      f"{('-e ' + hex(entry) + ' ') if entry else ''}"
      "$scripts -Map $out.map -o $out")
    w("  description = LD $out")
    w("")
    w("rule repack")
    w("  command = python3 tools/repack.py container $in $out")
    w("  description = REPACK $out")
    w("")
    w("rule verify")
    w(f"  command = python3 tools/verify.py orig/{VERSION} $in && touch $out")
    w("  description = VERIFY $in")
    w("")
    w("rule fndiff")
    w(f"  command = python3 tools/fndiff.py orig/{VERSION} $in; touch $out")
    w("  description = FNDIFF $in")
    w("")

    objs = []
    for p in asm:
        rel = p.relative_to(ROOT).as_posix()
        o = obj_path(p.relative_to(ROOT))
        w(f"build {o}: as {rel}")
        objs.append(o)
    w("")
    for p in src:
        cxx = is_cxx(p)
        rel = p.relative_to(ROOT).as_posix()
        o = obj_path(p.relative_to(ROOT))
        i = f"build/{rel}.i"
        s = f"build/{rel}.s"
        w(f"build {i}: cpp {rel}")
        w(f"  langflags = {' '.join(CPP_CXX_FLAGS if cxx else CPP_C_FLAGS)}")
        w(f"build {s}: {'ccplus' if cxx else 'cc'} {i}")
        w(f"build {o}: as {s}")
        objs.append(o)
    w("")

    targets = []
    for p in src:
        unit = unit_name(p)
        if not (ROOT / "asm" / "nonmatchings" / unit).is_dir():
            continue
        w(f"build build/target/{unit}.o: as asm/target/{unit}.s")
        targets.append(f"build/target/{unit}.o")
    if targets:
        w(f"build targets: phony {' '.join(targets)}")
    w("")

    extra = ["config/undefined_syms_auto.txt",
             "config/undefined_funcs_auto.txt",
             "config/discard.ld"]
    extra = [e for e in extra if (ROOT / e).exists()]
    scripts = extra + ["config/generated.ld"]

    for b in binf:
        rel = b.relative_to(ROOT).as_posix()
        o = obj_path(b.relative_to(ROOT))
        stub = f"build/{rel}.s"
        w(f"build {stub}: bin2s {rel}")
        w(f"build {o}: as {stub} | {rel}")
        objs.append(o)
    w("")

    linked = "build/linked.elf"
    elf = f"build/{VERSION}"
    w(f"build {linked}: link | {' '.join(objs + scripts)}")
    w(f"  scripts = {' '.join('-T ' + x for x in scripts)}")
    w("")
    w(f"build build/fndiff.stamp: fndiff {linked} | tools/fndiff.py")
    w("")
    w(f"build {elf}: repack {linked} | tools/repack.py "
      f"container/template.bin container/manifest.json || build/fndiff.stamp")
    w("")
    w(f"build build/verify.stamp: verify {elf} | tools/verify.py")
    w("")
    (ROOT / "build.ninja").write_text("\n".join(n))


def write_objdiff(src):
    cfg = {
        "$schema": "https://raw.githubusercontent.com/encounter/objdiff/"
                   "main/config.schema.json",
        "custom_make": "ninja",
        "custom_args": ["-k", "0"],
        "build_target": True,
        "build_base": True,
        "watch_patterns": ["*.c", "*.cpp", "*.h", "*.s", "*.inc",
                           "*.py", "*.yaml", "*.txt"],
        "units": [
            {
                "name": unit_name(p),
                "target_path": f"build/target/{unit_name(p)}.o",
                "base_path": obj_path(p.relative_to(ROOT)),
            }
            for p in src
            if (ROOT / "asm" / "target" / f"{unit_name(p)}.s").is_file()
        ],
    }
    (ROOT / "objdiff.json").write_text(json.dumps(cfg, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", action="store_true",
                    help="run splat before configuring")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean:
        subprocess.run(["rm", "-rf", "build", "asm", "assets", "container",
                        "build.ninja", "objdiff.json",
                        "config/generated.ld"], cwd=ROOT)
        return

    if args.split:
        subprocess.run(
            [sys.executable, "-m", "splat", "split",
             f"config/splat.{VERSION}.yaml"],
            cwd=ROOT, check=True)
        subprocess.run(
            [sys.executable, "tools/gen_target_yaml.py",
             f"config/splat.{VERSION}.yaml"],
            cwd=ROOT, check=True)
        subprocess.run(
            [sys.executable, "-m", "splat", "split",
             f"config/splat.{VERSION}.target.yaml"],
            cwd=ROOT, check=True)
        subprocess.run(
            [sys.executable, "tools/fix_vu0_asm.py", "asm"],
            cwd=ROOT, check=True)
        subprocess.run(
            [sys.executable, "tools/fix_asm_labels.py", "asm"],
            cwd=ROOT, check=True)
        subprocess.run(
            [sys.executable, "tools/extract_container.py",
             f"orig/{VERSION}", "container"],
            cwd=ROOT, check=True)

    cc1, cc1plus, cpp, launcher = find_compiler()
    asm, src, binf = collect_sources()
    if not asm and not src:
        sys.exit("no sources found -- run with --split first")
    check_units(src)

    need_c = any(not is_cxx(p) for p in src)
    need_cxx = any(is_cxx(p) for p in src)
    if need_c and cc1 is None:
        sys.exit("C sources present but no cc1 in this compiler tarball")
    if need_cxx and cc1plus is None:
        sys.exit("C++ sources present but no cc1plus in this compiler "
                 "tarball -- try another COMPILER_ID "
                 "(bash tools/setup.sh --list)")
    if src and cpp is None:
        sys.exit("no cpp in this compiler tarball; sources cannot be "
                 "preprocessed")

    write_ninja(asm, src, binf, cc1, cc1plus, cpp, launcher)
    write_objdiff(src)

    via = " (via wibo)" if launcher else ""
    if cc1:
        print(f"cc1:      {cc1}{via}")
    if cc1plus:
        print(f"cc1plus:  {cc1plus}{via}")
    print(f"configured {len(asm)} asm + {len(src)} source "
          f"+ {len(binf)} bin objects "
          f"({sum(1 for p in src if is_cxx(p))} C++)")
    print("run: ninja")


if __name__ == "__main__":
    main()