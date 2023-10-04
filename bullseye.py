import argparse
from utils.md5 import calculate_md5,validate_md5
from utils.extract_iso import extract_iso

def main():

	parser = argparse.ArgumentParser(description="Utility to aid in Resident Evil Dead Aim Reverse Engineering.")

	group = parser.add_mutually_exclusive_group(required=True)

	group.add_argument("--image", help="Path to the image file")
	group.add_argument("--extracted", help="Path to the local folder containing an already decompressed image contents")

	parser.add_argument("--output", help="Output directory (default: working_dir)", default="working_dir")
	args = parser.parse_args()

	# Check if either --image or --extracted is provided
	if args.image:
		print('Calculating the MD5 hash of the provided image...')
		md5 = calculate_md5(args.image)
		if (validate_md5(md5)):
			print('Extracting the image file...')
			extract_iso(args.image, args.output)
		else:
			print('Exiting...')

	else:
		print('Checking local file...')

if __name__ == "__main__":
	main()
