import sys, pyunpack

def extract_iso(iso_file, output_directory):
	try:
		archive = pyunpack.Archive(iso_file)
		files = archive.extractall(output_directory)
		total_files = len(files)

		for i, file in enumerate(files):
			progress = int(((i + 1) / total_files) * 100)
			sys.stdout.write(f"\rProgress: [{'#' * (progress // 2): <50}] {progress}%")
			sys.stdout.flush()

		print(f'\nISO extracted to: {output_directory}')
	except Exception as e:
		print(f'An error occurred: {str(e)}')
		