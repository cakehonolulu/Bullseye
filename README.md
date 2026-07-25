<p align="center">
    <img width=500px height=250px src="https://raw.githubusercontent.com/cakehonolulu/Bullseye/main/resources/banner800x.png" alt="Bullseye">
</p>

<br>

## Information

Bullseye is a tool to reverse engineer Resident Evil: Dead Aim.

From ripping the game assets (Such as audio files, model data, textures...) to (Hopefully) growing into a decompilation for the game.

## Status

The build reproduces `SLES_514.48` byte for byte. Everything the
console loads is assembled and linked from this repository; the ELF
container around it is carried from the original (see
[What "matching" means here](#what-matching-means-here)).

"Undecompiled code" is still assembly pulled in via `INCLUDE_ASM`.

## Progress

<!-- progress:start -->
**0.0030%** of the code is decompiled (40 / 1,328,837 bytes).

| File | Functions | Bytes |
|---|---:|---:|
| `src/text_0.c` | 1 | 40 |
<!-- progress:end -->

## Requirements

* **EE binutils** — `mips64r5900el-ps2-elf-as`, `-ld`, `-objdump` on
  `PATH`. Install from
  [ps2dev/ps2toolchain-ee](https://github.com/ps2dev/ps2toolchain-ee).
* **Python 3**
* **An original dump of the game.**

## Getting started

**1. Fetch the ee-gcc toolchain**

```sh
bash tools/setup.sh
```

Downloads the period compiler (`ee-gcc2.9-991111-01`) from
[decompme/compilers](https://github.com/decompme/compilers), plus
`objdiff-cli`, `m2c` and `decomp-permuter`, and installs `splat` and
`ninja`. Everything lands in `tools/` and is gitignored.

**2. Extract the executable from your disc image**

`SLES_514.48` sits in the root of the disk.

Put it at `orig/SLES_514.48` and check it:

```sh
sha1sum orig/SLES_514.48
# dc5b5172c9be651c476fea0e7620e47775c9dd81
```

A different hash means a different region or revision, and the config in
`config/` will not apply.

**3. Build**

```sh
python3 configure.py --split
ninja
```

`--split` runs splat, patches VU0 operand syntax for modern gnu-as, and
extracts the ELF container. You only need to re-run it after changing
`config/splat.SLES_514.48.yaml` or `config/symbol_addrs.txt`.

**4. Confirm the match**

A successful build ends with:

```
REPACK build/SLES_514.48
  sha1     dc5b5172c9be651c476fea0e7620e47775c9dd81
  expected dc5b5172c9be651c476fea0e7620e47775c9dd81
  OK -- byte-identical to the original
VERIFY build/SLES_514.48
MATCH -- every byte the original loads is reproduced exactly
```

`build/SLES_514.48` is then interchangeable with the original, and should boot
in PCSX2:

```sh
pcsx2 -elf $PWD/build/SLES_514.48 <image.iso>
```

## What "matching" means here

Two separate checks run on every build.

`tools/verify.py` compares the **loadable image** — every byte either
`PT_LOAD` maps into memory. This is the one that says the code and data
are correct.

`tools/repack.py` substitutes that image into the container extracted
from the original and checks a whole-file sha1. The container itself is
carried, not rebuilt: it holds section headers, `.gnu.linkonce.*` COMDATs,
and the `.DVP.*` VU1 microcode overlays that SCE's `dvp-as` produced. Those, we can't reproduce.

## Supported hashes

sha256 e78aed719c50b73b8f065698d1a3b6c866ae7bd5e5b460af536a34f1e0eb6956  RESIDENT_EVIL_DEAD_AIM.ISO (Dump from Retail DVD)

sha1 dc5b5172c9be651c476fea0e7620e47775c9dd81  SLES_514.48 (PAL executable)

![Alt](https://repobeats.axiom.co/api/embed/ca26df06fed1f2b712443d2764f1af0eb36f3b53.svg "Repobeats analytics image")