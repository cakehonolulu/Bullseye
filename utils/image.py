import sys, magic, os, patoolib, shutil

def detect_image_type(file_path):
	magic_obj = magic.Magic(mime=True)
	file_type = magic_obj.from_file(file_path)
	return file_type

def extract_image(image, image_type, output):
	if (image_type == "iso"):
		extract_iso(image, output)
	else:
		print(f"Unhandled extraction for image type: {image_type}")
		quit()

def extract_iso(iso_file, output_directory):
	try:
		if os.path.exists(output_directory):
			if os.listdir(output_directory):
				user_response = input(f"The directory '{output_directory}' is not empty. Do you want to remove its contents? (y/n): ")
				if user_response.lower() == 'y':
					for item in os.listdir(output_directory):
						item_path = os.path.join(output_directory, item)
						if os.path.isfile(item_path):
							os.remove(item_path)
						elif os.path.isdir(item_path):
							shutil.rmtree(item_path)
				else:
					print("Extraction canceled.")
					quit()
		else:
			print("Creating output directory...", flush=True)
			os.makedirs(output_directory)

		print("Extracting the ISO file...", flush=True)
		
		patoolib.extract_archive(iso_file, outdir=output_directory, verbosity=0)

		print("ISO extracted!")
	
	except Exception as e:
		print(f"An error occurred: {str(e)}")
		