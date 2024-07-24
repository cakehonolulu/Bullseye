
import os

def apply(config, args):
    config["baseimg"] = ""
    config["myimg"] = ""
    config["arch"] = "mipsee"
    config["objdump_executable"] = "mips64r5900el-ps2-elf-objdump"
    config["disassemble_all"] = True
