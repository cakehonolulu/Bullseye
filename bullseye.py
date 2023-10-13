import argparse
from utils.md5 import calculate_md5,validate_md5
from utils.image import detect_image_type,extract_image

def main():

	parser = argparse.ArgumentParser(description="Utility to aid in Resident Evil Dead Aim Reverse Engineering.")

	group = parser.add_mutually_exclusive_group(required=True)

	group.add_argument("--image", help="Path to the image file")
	group.add_argument("--extracted", help="Path to the local folder containing an already decompressed image contents")

	parser.add_argument("--output", help="Output directory (default: working_dir)", default="working_dir")
	args = parser.parse_args()

	# Check if either --image or --extracted is provided
	if args.image:
		print("Detecting image type... ", end="")

		file_type = detect_image_type(args.image)
		image_type = None

		if file_type:
			if file_type == "application/x-iso9660-image":
				print("ISO image detected!")
				image_type = "iso"
			else:
				print(f"Unsupported file type: {file_type}")
				quit()
		else:
			print("Unable to determine the file type.")
			quit()


		print("Calculating the MD5 of the image file... ", end="", flush=True)

		if (validate_md5(args.image, image_type)):
			print("Valid hash found!")
			extract_image(args.image, image_type, args.output)
		else:
			print("Unrecognized MD5! Exiting...")

	elif args.extracted:
		print("Using the an already extracted copy...")


if __name__ == "__main__":
	main()
