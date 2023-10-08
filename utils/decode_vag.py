import struct, sys
import numpy as np

class SonyAdpcm:
    def __init__(self):
        self.VAGLut = np.array([
            [0.0, 0.0],
            [60.0 / 64.0, 0.0],
            [115.0 / 64.0, -52.0 / 64.0],
            [98.0 / 64.0, -55.0 / 64.0],
            [122.0 / 64.0, -60.0 / 64.0]
        ])

        self.VAG_SAMPLE_BYTES = 14
        self.VAG_SAMPLE_NIBBLE = self.VAG_SAMPLE_BYTES * 2

    def decode(self, vag_data):
        pcm_data = bytearray()

        vag_reader = bytearray(vag_data)
        vag_reader_offset = 0

        hist_1 = 0.0
        hist_2 = 0.0

        # Skip header
        vag_reader_offset += 16

        # Start decoding
        while vag_reader_offset < len(vag_reader):
            # Read chunk data
            decoding_coefficient = vag_reader[vag_reader_offset]
            vag_reader_offset += 1

            shift = decoding_coefficient & 0xF
            predict = (decoding_coefficient & 0xF0) >> 4

            flags = vag_reader[vag_reader_offset]
            vag_reader_offset += 1

            sample = vag_reader[vag_reader_offset:vag_reader_offset+self.VAG_SAMPLE_BYTES]
            vag_reader_offset += self.VAG_SAMPLE_BYTES

            if flags == 7:
                break
            elif flags == 6:
                loop_offset = len(pcm_data)
            else:
                samples = np.zeros(self.VAG_SAMPLE_NIBBLE, dtype=int)

                # expand 4bit -> 8bit
                for j in range(self.VAG_SAMPLE_BYTES):
                    samples[j * 2] = sample[j] & 0xF
                    samples[j * 2 + 1] = (sample[j] & 0xF0) >> 4

                # Decode samples
                for j in range(self.VAG_SAMPLE_NIBBLE):
                    # shift 4 bits to top range of int16_t
                    s = samples[j] << 12
                    if s & 0x8000:
                        s |= -0x10000

                    predict = min(predict, self.VAGLut.shape[0] - 1)

                    sample = (s >> shift) + hist_1 * self.VAGLut[predict, 0] + hist_2 * self.VAGLut[predict, 1]
                    hist_2 = hist_1
                    hist_1 = sample

                    pcm_data.extend(struct.pack('<h', max(min(int(sample), 32767), -32768)))

        return pcm_data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("./adpcm_decode.py <input_file> <output_file>")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]

        with open(input_file, 'rb') as file:
            vag_data = file.read()

        # Call the decode method to get PCM data
        decoder = SonyAdpcm()
        pcm_data = decoder.decode(vag_data)

        # Save the PCM data to output.raw
        with open(output_file, 'wb') as file:
            file.write(pcm_data)

        print(f"Decoding completed. PCM data saved to {output_file}")
