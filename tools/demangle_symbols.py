import subprocess

# Path to the demangle program
demangle_program = "../ccc/bin/demangle"

# Path to the file containing mangled symbols
symbols_file = "symbols.txt"

# Read each mangled symbol from the file and demangle
with open(symbols_file, 'r') as f:
    for line in f:
        mangled_symbol = line.strip()
        command = [demangle_program, mangled_symbol]

        try:
            demangled_output = subprocess.check_output(command, universal_newlines=True)
            print(f"Original: {mangled_symbol}")
            print(f"Demangled: {demangled_output}\n")
        except subprocess.CalledProcessError as e:
            print(f"Error demangling {mangled_symbol}: {e}\n")
