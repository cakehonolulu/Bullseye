import json
import os
import sys
import hashlib
import binascii

def calculate_sha1(file_path):
    sha1_hash = hashlib.sha1()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha1_hash.update(byte_block)
    return sha1_hash.hexdigest()

def print_bytes(byte_str):
    for i in range(0, len(byte_str), 2):
        print(byte_str[i:i+2], end=' ')
    print()

def replace_binary_parts(replacements, base_directory, target_bin_path):
    with open(target_bin_path, 'r+b') as target_binary_file:
        for replacement in replacements:
            file_path = os.path.join(base_directory, 'build', replacement['file_path'])  # Look in the build/ folder
            offset = int(replacement['offset'], 16)
            expected_size = replacement['expected_size']

            with open(file_path, 'rb') as binary_file:
                replacement_bytes = binary_file.read()
                actual_size = len(replacement_bytes)

                if actual_size != expected_size:
                    print(f"Expected size ({expected_size} bytes) does not match actual size ({actual_size} bytes) for {file_path}")
                    continue

            # Seek to the offset and write the replacement bytes
            target_binary_file.seek(offset)
            target_binary_file.write(replacement_bytes)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 replace.py <target_bin_path>")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_bin_path = sys.argv[1]

    # Calculate the SHA-1 hash of the provided binary
    target_bin_hash = calculate_sha1(target_bin_path)

    known_exec_hashes = {
        "dc5b5172c9be651c476fea0e7620e47775c9dd81": "SLES_514.48",  # PAL Executable, SLES_514.48
        # Add other known hashes as needed
    }

    replacements_file = known_exec_hashes.get(target_bin_hash)
    if not replacements_file:
        print("Unknown binary version")
        sys.exit(1)

    version = None
    if replacements_file == "SLES_514.48":
        version = "pal"

    if version is None:
        print("Unhandled error, no binary version found!")
        sys.exit(1)

    replacements_file_path = os.path.join(script_dir, f"{version}_map.json")

    if not os.path.exists(replacements_file_path):
        print(f"Replacements file not found for the detected binary version: {replacements_file} ({version} region)")
        sys.exit(1)

    with open(replacements_file_path, 'r') as config_file:
        config_data = json.load(config_file)
        replacements = config_data['replacements']
        replace_binary_parts(replacements, script_dir, target_bin_path)
