import sys
import hashlib
from utils.known_hashes import known_iso_hashes

def calculate_md5(file_path):
	md5 = hashlib.md5()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(8192 * 8), b""):
			md5.update(chunk)
	return md5.hexdigest()

def validate_md5(file_path, image_type):
	md5 = calculate_md5(file_path)
	if (image_type == "iso"):
		if md5 in known_iso_hashes:
			return True
		else:
			print(f"The calculated MD5 hash ({md5}) for the type '{image_type}' is unrecognized, open an issue on GitHub")
			return False
