import os

def apply(config, args):
    config["baseimg"] = "target.bin"
    config["myimg"] = "entry.bin"
    config["arch"] = "mips"
    config["objdump_flags"] = ["-m", "mips:5900", "-Dz", "-bbinary", "-EL"]
    config["disassemble_all"] = True
