import os
import shutil
import subprocess

# Get the absolute path of the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Directory containing the .S files
source_directory = os.path.join(script_dir, 'ps2')

# Output directory for the binary dumps
output_directory = os.path.join(script_dir, 'build')

def compile_and_dump(file_path):
	# Build the assembly file and output the .o file to the build directory
	output_object_path = os.path.join(output_directory, 'temp.o')

	# Run the mipsel-none-elf-as command and capture the output
	result = subprocess.run(['mipsel-none-elf-as', '-march=5900', '-EL', '-o', output_object_path, file_path],
							stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

	# Print custom message with the file name being compiled
	print(f"[MIPS-AS] {os.path.basename(file_path)}")

	# Print standard output and standard error only if there's an error
	if result.returncode != 0:
		if result.stdout:
			print("Standard Output:")
			print(result.stdout)

		if result.stderr:
			print("Standard Error:")
			print(result.stderr)

	# Convert to binary
	subprocess.run(['mipsel-none-elf-objcopy', '-O', 'binary', '-j', '.text', '-R', '.note', '-R', '.comment', '-S', output_object_path, 'temp.bin'])

	# Move the resulting binary to the output directory
	output_path = os.path.join(output_directory, os.path.basename(file_path)[:-2] + '.bin')
	os.rename('temp.bin', output_path)

print(f"Output directory: {output_directory}")
print("Compiling...")

# Create or clear the build directory
if os.path.exists(output_directory):
	# Clear the contents of the directory
	for file in os.listdir(output_directory):
		file_path = os.path.join(output_directory, file)
		try:
			if os.path.isfile(file_path):
				os.unlink(file_path)
			elif os.path.isdir(file_path):
				shutil.rmtree(file_path)
		except Exception as e:
			print(f"Failed to delete {file_path}: {e}")
else:
	# Create the directory
	os.makedirs(output_directory)

# Iterate through .S files and compile/dump them
for filename in os.listdir(source_directory):
	if filename.endswith('.S'):
		file_path = os.path.join(source_directory, filename)
		compile_and_dump(file_path)
