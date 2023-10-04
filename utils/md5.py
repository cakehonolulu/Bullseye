import sys
import hashlib
from utils.extract_iso import extract_iso
from utils.known_hashes import known_hashes

def calculate_md5(file_path):
	md5 = hashlib.md5()
	with open(file_path, 'rb') as f:
		for chunk in iter(lambda: f.read(8192 * 8), b''):
			md5.update(chunk)
	return md5.hexdigest()

def validate_md5(md5):
	if md5 in known_hashes:
		print(f'Found valid hash: {md5}')
		return True
	else:
		print('The calculated MD5 hash ({md5}) is unrecognized, open an issue on GitHub')
		return False
