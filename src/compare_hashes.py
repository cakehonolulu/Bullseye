import os
import hashlib
import json
import subprocess

# Define file paths
root_dir = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
working_dir = os.path.join(root_dir, 'working_dir')
source_dir = os.path.join(root_dir, 'src')
build_dir = os.path.join(source_dir, 'build')
binary_file_path = os.path.join(working_dir, 'SLES_514.48')
pal_map_path = os.path.join(source_dir, 'pal_map.json')

def read_bytes_from_file(file_path, offset, size):
    with open(file_path, 'rb') as f:
        f.seek(offset)
        return f.read(size)

def compute_hash(data):
    return hashlib.sha256(data).hexdigest()

def run_objdump(file_path):
    result = subprocess.run(['mips64r5900el-ps2-elf-objdump', '-d', file_path],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout if result.returncode == 0 else result.stderr

def main():
    # Load pal_map.json
    with open(pal_map_path, 'r') as f:
        pal_map = json.load(f)

    for replacement in pal_map['replacements']:
        file_path = replacement['file_path']
        offset = int(replacement['offset'], 16)
        expected_size = replacement['expected_size']

        # Read bytes from working_dir binary file
        extracted_bytes = read_bytes_from_file(binary_file_path, offset, expected_size)

        # Write extracted_bytes to a temporary binary file
        temp_extracted_path = os.path.join(working_dir, 'temp.bin')
        with open(temp_extracted_path, 'wb') as f:
            f.write(extracted_bytes)

        extracted_hash = compute_hash(extracted_bytes)

        # Read bytes from build directory binary file
        build_file_path = os.path.join(build_dir, file_path)
        build_bytes = read_bytes_from_file(build_file_path, 0, expected_size)
        build_hash = compute_hash(build_bytes)

        # Compare hashes
        if extracted_hash == build_hash:
            print(f"Match: {file_path} (offset: {offset}, size: {expected_size})")
        else:
            print(f"Mismatch: {file_path} (offset: {offset}, size: {expected_size})")
            print(f"Extracted Hash: {extracted_hash}")
            print(f"Build Hash: {build_hash}")
            
            # Run objdump for both files
            extracted_file_temp = os.path.join(working_dir, 'extracted_temp.bin')
            build_file_temp = os.path.join(build_dir, 'build_temp.bin')
            
            with open(extracted_file_temp, 'wb') as f:
                f.write(extracted_bytes)
            with open(build_file_temp, 'wb') as f:
                f.write(build_bytes)
            
            extracted_objdump = run_objdump(extracted_file_temp)
            build_objdump = run_objdump(build_file_temp)
            
            print("\n--- Extracted Objdump ---")
            print(extracted_objdump)
            print("\n--- Build Objdump ---")
            print(build_objdump)
            
            # Clean up temporary files
            os.remove(extracted_file_temp)
            os.remove(build_file_temp)

if __name__ == "__main__":
    main()
