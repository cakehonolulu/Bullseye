import os
import hashlib
import json
import subprocess
import sys
import tempfile
from typing import Optional
from pathlib import Path
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Window
from prompt_toolkit.formatted_text import ANSI

# Define file paths
root_dir = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
working_dir = os.path.join(root_dir, 'working_dir')
source_dir = os.path.join(root_dir, 'src')
build_dir = os.path.join(source_dir, 'build')
binary_file_path = os.path.join(working_dir, 'SLES_514.48')
pal_map_path = os.path.join(source_dir, 'pal_map.json')
asm_differ_dir = os.path.join(root_dir, 'external', 'asm-differ')

sys.path.append(asm_differ_dir)
def read_bytes_from_file(file_path, offset, size):
    with open(file_path, 'rb') as f:
        f.seek(offset)
        return f.read(size)

def compute_hash(data):
    return hashlib.sha256(data).hexdigest()

my_env = os.environ.copy()

def update_diff_settings(baseimg_path: str, myimg_path: str,
                         baseimg_base_addr: Optional[int] = None, baseimg_end_addr: Optional[int] = None) -> None:
    my_env["DIFF_BASEIMG"] = baseimg_path
    my_env["DIFF_MYIMG"] = myimg_path
    my_env["DIFF_ARCH"] = "mipsee"
    my_env["DIFF_OBJDUMP_BIN"] = "mips64r5900el-ps2-elf-objdump"
    my_env["DIFF_DISS_ALL"] = "True"

    if baseimg_base_addr is not None and baseimg_end_addr is not None:
        my_env["DIFF_BASE_IMG_BASE"] = hex(baseimg_base_addr)
        my_env["DIFF_BASE_IMG_END"] = hex(baseimg_end_addr)
        my_env["DIFF_BASE_IMG_NAME"] = str(os.path.basename(baseimg_path))

def run_asm_differ(baseimg_path, myimg_path, offset, size):
    # Define start and end arguments for diff.py
    start = offset
    end = offset + size

    # Update diff_settings.py
    update_diff_settings(baseimg_path, myimg_path, start, end)

    # Construct the command for asm-differ
    diff_command = [
        sys.executable,
        os.path.join(asm_differ_dir, 'diff.py'),
        "0"
    ]

    # Run the diff command in the context of src_dir
    try:
        result = subprocess.run(diff_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=source_dir, check=True, env=my_env)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print("Error running diff.py:")
        print("Return code:", e.returncode)
        print("Error output:")
        print(e.stderr)
        return e.stderr

def display_comparisons():
    # Load pal_map.json
    with open(pal_map_path, 'r') as f:
        pal_map = json.load(f)

    comparisons = []
    matches = []

    for replacement in pal_map['replacements']:
        file_path = replacement['file_path']
        offset = int(replacement['offset'], 16)
        expected_size = replacement['expected_size']

        # Read bytes from working_dir binary file
        extracted_bytes = read_bytes_from_file(binary_file_path, offset, expected_size)
        extracted_hash = compute_hash(extracted_bytes)

        # Read bytes from build directory binary file
        build_file_path = os.path.join(build_dir, file_path)
        build_bytes = read_bytes_from_file(build_file_path, 0, expected_size)
        build_hash = compute_hash(build_bytes)

        # Compare hashes
        if extracted_hash != build_hash:
            asm_differ_output = run_asm_differ(binary_file_path, build_file_path, offset, expected_size)
            
            comparisons.append((file_path, offset, expected_size, asm_differ_output))
        else:
            matches.append((file_path, offset, expected_size))
    
    return comparisons, matches

def main_menu(comparisons, matches):
    kb = KeyBindings()
    menu_state = {'current_index': 0, 'show_diff': False, 'current_comparison': None}

    @kb.add('up')
    def up(event):
        if menu_state['current_index'] > 0:
            menu_state['current_index'] -= 1
            app.invalidate()

    @kb.add('down')
    def down(event):
        if menu_state['current_index'] < len(comparisons) - 1:
            menu_state['current_index'] += 1
            app.invalidate()

    @kb.add('enter')
    def enter(event):
        if menu_state['current_index'] < len(comparisons):
            menu_state['show_diff'] = True
            menu_state['current_comparison'] = comparisons[menu_state['current_index']]
            app.layout = get_layout()  # Force layout rebuild
            app.invalidate()

    def back(event):
        menu_state['show_diff'] = False
        menu_state['current_comparison'] = None
        app.layout = get_layout()  # Force layout rebuild
        app.invalidate()

    @kb.add('q')
    def quit_or_back(event):
        if menu_state['show_diff']:
            back(event)
        else:
            app.exit()

    @kb.add('c-c')
    def quit_ctrl_c(event):
        app.exit()

    def get_main_menu_content():
        content = "Non-matching comparisons:\n"
        for idx, (file_path, offset, size, _) in enumerate(comparisons):
            selected_marker = '>' if idx == menu_state['current_index'] else ' '
            content += f"{selected_marker} {file_path} (Offset: {'0x{:X}'.format(offset)}, Size: {size})\n"
        
        content += "\nMatching comparisons:\n"
        for file_path, offset, size in matches:
            content += f"  {file_path} (Offset: {'0x{:X}'.format(offset)}, Size: {size})\n"
        
        return content

    def get_layout():
        if menu_state['show_diff']:
            if menu_state['current_comparison']:
                file_path, offset, size, asm_differ_output = menu_state['current_comparison']
                content = ANSI(f"--- ASM Differ Output ---\n{asm_differ_output}")
            else:
                content = "--- No comparison selected ---"
            return Layout(
                HSplit([
                    Window(content=FormattedTextControl(text=lambda: content), height=20, width=80)
                ]),
                focused_element=None
            )
        else:
            return Layout(
                HSplit([
                    Window(content=FormattedTextControl(text=lambda: get_main_menu_content()), height=20, width=80)
                ]),
                focused_element=None
            )

    global app
    app = Application(layout=get_layout(), key_bindings=kb, full_screen=True)

    try:
        app.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    comparisons, matches = display_comparisons()
    if comparisons:
        main_menu(comparisons, matches)
    else:
        print("No mismatches found.")
