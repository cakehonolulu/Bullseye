import os,sys

def extract_fpk(file_path, output_directory, offset, fpk_name):
    has_lst = False

    with open(file_path, 'rb') as fpk:
        fpk.seek(offset)

        fpk_off = fpk.tell()

        # Check if it's a valid FPK file
        fpk_ident_bytes = fpk.read(4)
        if fpk_ident_bytes != b'fpk\0':
            print("Invalid FPK file.")
            return

        
        zero = int.from_bytes(fpk.read(4), byteorder='little')
        files = int.from_bytes(fpk.read(4), byteorder='little')
        block_sz = int.from_bytes(fpk.read(4), byteorder='little')
        head_size = int.from_bytes(fpk.read(4), byteorder='little')
        info_offset = int.from_bytes(fpk.read(4), byteorder='little') + fpk_off
        info_size = int.from_bytes(fpk.read(4), byteorder='little')
        zero = int.from_bytes(fpk.read(4), byteorder='little')
        zero = int.from_bytes(fpk.read(4), byteorder='little')
        dummy = int.from_bytes(fpk.read(4), byteorder='little')  # 0 or 1
        base_offset = int.from_bytes(fpk.read(4), byteorder='little') + fpk_off
        bin_size = int.from_bytes(fpk.read(4), byteorder='little')

        fpk.seek(info_offset)
        
        for i in range(files):
            zero = int.from_bytes(fpk.read(4), byteorder='little')  # It was always zero
            offset = int.from_bytes(fpk.read(4), byteorder='little')
            size = int.from_bytes(fpk.read(4), byteorder='little')
            ext_ = fpk.read(4)
            
            ext_str = ext_.decode('utf-8')[::-1]

            offset += base_offset
            
            if ext_str == "lst":
                has_lst = True
                memory_file = fpk.read(size)
                names = memory_file.decode('utf-8').splitlines()
            else:
                has_lst = False
            
            if not has_lst:
                file_name = os.path.join(output_directory, f"{fpk_name}#{i}.{ext_str}")
            else:
                file_name = os.path.join(output_directory, f"{fpk_name}#{names[i]}")
            
            file_name = file_name.replace("..", "")
            file_name = file_name.replace("\x00", "")
           
            tmp = fpk.tell()

            fpk.seek(offset)
            signature = fpk.read(4)
            
            fpk.seek(tmp)

            if signature == b'fpk\0':
                extract_fpk(file_path, output_directory, offset, fpk_name)
            else:
                with open(file_name, 'wb') as output_file:
                    if (1==2): print(f"  {offset:08x} {size}     {file_name.replace(f'{output_directory}/', '')} ")
                    tmp = fpk.tell()
                    fpk.seek(offset)
                    output_file.write(fpk.read(size))
                    fpk.seek(tmp)

def find_fpk_name(fpk_file):
    with open(fpk_file, 'rb') as fpk:
        fpk.seek(64)
        fpk_name = ""

        while True:
            char = fpk.read(1)
            if char == b'\x00' or not char:
                break
            fpk_name += char.decode('utf-8')

        print(f"FPK Archive File: {fpk_name}")

        fpk.close()
        return fpk_name


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("./fpk.py <file> <output_dir>")
    else:
        fpk_file = sys.argv[1]
        output_directory = sys.argv[2]

        if os.path.exists(fpk_file):
            print(f"Processing {fpk_file} ...")
            if not os.path.exists(output_directory):
                os.makedirs(output_directory)
            
            fpk_name = find_fpk_name(fpk_file)

            extract_fpk(fpk_file, output_directory, 0, fpk_name)
        else:
            print("File not found, exiting...")
