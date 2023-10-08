import os, sys
from tabulate import tabulate

class ADPCMChannel:
	MAX_BLOCK = 65536

	def __init__(self):
		self.ChannelBuffer = [0] * self.MAX_BLOCK
		self.InputFileReadOffset = 0
		self.InputDoneOffset = 0
		self.InputDoneOffsetSaveForLoop = 0
		self.InputBufferReadOffset = 0
		self.OutputBufferWriteOffset = 0
		self.StartOffset = 0
		self.PreviousSample = 0.0
		self.CurrentSample = 0.0
		self.PreviousSampleShort = 0
		self.CurrentSampleShort = 0
		self.FileBinaryReader = None
		self.APDCM_Info = [0] * 16
		self.Index = 0
		self.StepSize = 0
		self.Predictor = 0
		self.y0 = 0
		self.y1 = 0


class ADPCMFile:
	class ADPCM_TYPE:
		PS2_INTERLEAVE = 0
		SS2 = 1
		MIB = 2
		STR2 = 3
		PS2_WITHHEADER = 4

	def __init__(self):
		self.SampleRate = 0
		self.NbOfChannels = 0
		self.ChannelLeft = ADPCMChannel()
		self.ChannelRight = ADPCMChannel()
		self.BufferLength = 0
		self.ADPCMType = None
		self.FileLength = 0
		self.ContainerFileLength = 0
		self.Interleave = 0
		self.CanLoop = False
		self.LoopSet = False
		self.TotalSamples = 0
		self.NbSamplesPlayed = 0
		self.LoopStart = 0
		self.LoopLength = 0
		self.LoopEnd = 0
		self.LoopStartSample = 0
		self.HalpSize = 0
		self.StartOffset = 0
		self.BitsPerSamples = 0
		self.Compressed = False
		self.PlayContinuous = False
		self.FileName = ""
		self.SourcePath = ""
		self.NumOfLoops = 0
		self.EAXACompression = 0
		self.EAXASplit = 0
		self.EAXASplitCompression = 0
		self.XABits = 0
		self.EOR = False
		self.HasHeader = True
		self.DataCount = 18
		self.XAPlayed = 0

	def __str__(self):
		return (f"ADPCMFile Details:\n"
				f"SampleRate: {self.SampleRate}\n"
				f"NbOfChannels: {self.NbOfChannels}\n"
				f"ChannelLeft: {self.ChannelLeft}\n"
				f"ChannelRight: {self.ChannelRight}\n"
				f"BufferLength: {self.BufferLength}\n"
				f"ADPCMType: {self.ADPCMType}\n"
				f"FileLength: {self.FileLength}\n"
				f"ContainerFileLength: {self.ContainerFileLength}\n"
				f"Interleave: {self.Interleave}\n"
				f"CanLoop: {self.CanLoop}\n"
				f"LoopSet: {self.LoopSet}\n"
				f"TotalSamples: {int(self.TotalSamples)}\n"
				f"NbSamplesPlayed: {self.NbSamplesPlayed}\n"
				f"LoopStart: {self.LoopStart}\n"
				f"LoopLength: {self.LoopLength}\n"
				f"LoopEnd: {self.LoopEnd}\n"
				f"LoopStartSample: {self.LoopStartSample}\n"
				f"HalpSize: {self.HalpSize}\n"
				f"StartOffset: {self.StartOffset}\n"
				f"BitsPerSamples: {self.BitsPerSamples}\n"
				f"Compressed: {self.Compressed}\n"
				f"PlayContinuous: {self.PlayContinuous}\n"
				f"FileName: {self.FileName}\n"
				f"SourcePath: {self.SourcePath}\n"
				f"NumOfLoops: {self.NumOfLoops}\n"
				f"EAXACompression: {self.EAXACompression}\n"
				f"EAXASplit: {self.EAXASplit}\n"
				f"EAXASplitCompression: {self.EAXASplitCompression}\n"
				f"XABits: {self.XABits}\n"
				f"EOR: {self.EOR}\n"
				f"HasHeader: {self.HasHeader}\n"
				f"DataCount: {self.DataCount}\n"
				f"XAPlayed: {self.XAPlayed}")

class CDXA_File:
	def __init__(self, begin_sector, end_sector, channel, file_size, total_samples, coding_info):
		self.BeginSector = begin_sector
		self.EndSector = end_sector
		self.Channel = channel
		self.FileSize = file_size
		self.TotalSamples = total_samples
		self.CodingInfo = coding_info


class Ripper:
	def __init__(self):
		self.m_bolStop = False
		self.m_CheckForInterleave = False
		self.m_XASearchEmtyBuffer = False
		self.file_table = []

	@property
	def StopProcessNow(self):
		return self.m_bolStop

	@StopProcessNow.setter
	def StopProcessNow(self, value):
		self.m_bolStop = value

	@property
	def CheckForInterleave(self):
		return self.m_CheckForInterleave

	@CheckForInterleave.setter
	def CheckForInterleave(self, value):
		self.m_CheckForInterleave = value

	@property
	def XASearchEmptyBuffer(self):
		return self.m_XASearchEmtyBuffer

	@XASearchEmptyBuffer.setter
	def XASearchEmptyBuffer(self, value):
		self.m_XASearchEmtyBuffer = value

	def ReadInt(self, buffer, offset):
		return (buffer[offset + 1] << 8) | buffer[offset]

	def ReadLong(self, buffer, offset):
		return (buffer[offset + 3] << 24) | (buffer[offset + 2] << 16) | (buffer[offset + 1] << 8) | buffer[offset]

	def ReadIntLE(self, buffer, offset):
		return (buffer[offset] << 8) | buffer[offset + 1]

	def ReadLongLE(self, buffer, offset):
		return (buffer[offset] << 24) | (buffer[offset + 1] << 16) | (buffer[offset + 2] << 8) | buffer[offset + 3]

	def HINIBBLE(self, bByte):
		return (bByte >> 4) & 0xF

	def LONIBBLE(self, bByte):
		return bByte & 0xF

	def dump_file_table(self):
		print(tabulate(self.file_table, headers=['ADPCM Type', 'Start Offset (Hex)'], tablefmt='fancy_grid'))

	def fileFound(self, file):
		adpcm_type = self.ADPCM_TYPE_NAMES.get(file.ADPCMType, 'Unknown')
		self.file_table.append([adpcm_type, hex(file.StartOffset)])

	ADPCM_TYPE_NAMES = {
		0: 'PS2_INTERLEAVE',
		1: 'SS2',
		2: 'MIB',
		3: 'MIC',
		4: 'STR2',
		5: 'PS2_WITHHEADER'
	}

	def RipFile(self, sFullPath):
		buffer = bytearray(32768)
		num = 0
		num2 = 32768
		num3 = 0
		ADPCMFile_ = None
		num4 = 0
		flag = False
		flag2 = True
		b = 2
		num5 = 0
		num6 = 0
		num7 = 0
		num8 = 0
		num9 = 0
		self.StopProcessNow = False

		with open(sFullPath, 'rb') as stream:
			# Move the file handle to the end of the file
			stream.seek(0, 2)

			# Calculate the file size 
			length = stream.tell()
			stream.seek(0)

			# Read the header bytes
			buffer[:] = stream.read(60)

			if buffer[0] == 82 and buffer[1] == 73 and buffer[2] == 70 and buffer[3] == 70 and buffer[8] == 67 and buffer[9] == 68 and buffer[10] == 88 and buffer[11] == 65:
				print("CDXA detected, unsupported!")
				return

			stream.seek(0)

			if (ADPCMFile_ == None):
				while True:
					num = num2

					buffer[:] = stream.read(num2)

					num6 = stream.tell()

					ADPCMFile_ = None
					
					if (stream.tell() == length):
						break

					for num12 in range(0, num - 128, 2):
						if (buffer[num12] == 83 and
							buffer[num12 + 1] == 83 and
							buffer[num12 + 2] == 104 and
							buffer[num12 + 3] == 100 and
							buffer[num12 + 32] == 83 and
							buffer[num12 + 33] == 83 and
							buffer[num12 + 34] == 98 and
							buffer[num12 + 35] == 100
						):
							print("Unimplemented SS2 File")
							break
						
						if (buffer[num12] == 83 and
							buffer[num12 + 1] == 84 and
							buffer[num12 + 2] == 82 and
							buffer[num12 + 3] == 50 and
							buffer[num12 + 20] == 32 and
							buffer[num12 + 21] == 97 and
							buffer[num12 + 22] == 117 and
							buffer[num12 + 23] == 100 and
							buffer[num12 + 24] == 105 and
							buffer[num12 + 25] == 111
						):
							print("Unimplemented STR2 File")
							break

						if (num12 % 16 == 0 and
							buffer[num12 + 1] == 64 and
							buffer[num12 + 2] <= 100 and
							buffer[num12 + 3] == 0 and
							(self.ReadInt(buffer, num12 + 8) == 22050 or
							self.ReadInt(buffer, num12 + 8) == 48000 or
							self.ReadInt(buffer, num12 + 8) == 17580 or
							self.ReadInt(buffer, num12 + 8) == 47999) and
							buffer[num12 + 10] == 0
						):
							print("Unimplemented PS2_WITH_HEADER File")
							break
					
					flag9 = False

					if (ADPCMFile_ == None and self.m_CheckForInterleave):
						num7 = 0

						for num16 in range(0, num - 128, 16):
							b = 0
							flag2 = True

							if (self.HINIBBLE(buffer[num16 + 16]) >= 5 or
								self.LONIBBLE(buffer[num16 + 16]) > 12 or
								buffer[num16 + 16] == 0 or
								buffer[num16 + 17] >= 7
							):
								continue

							for j in range(16):
								if j != 1 and buffer[num16 + j] != 0:
									flag2 = False

							if flag2:
								b = 1

							num8 = stream.tell() - num2 + num16

							num5 = 0

							while True:
								if (buffer[num16 + 1] == 7 and
									buffer[num16 + 2] == 119 and
									buffer[num16 + 3] == 119 and
									buffer[num16 + 4] == 119 and
									buffer[num16 + 5] == 119 and
									buffer[num16 + 6] == 119 and
									buffer[num16 + 7] == 119 and
									buffer[num16 + 8] == 119 and
									buffer[num16 + 9] == 119 and
									buffer[num16 + 10] == 119 and
									buffer[num16 + 11] == 119 and
									buffer[num16 + 12] == 119 and
									buffer[num16 + 13] == 119 and
									buffer[num16 + 14] == 119
								):
									flag = True
									break

								if (self.HINIBBLE(buffer[num16]) > 5 or
									self.LONIBBLE(buffer[num16]) > 12 or
									buffer[num16 + 1] > 7
								):
									break

								num16 += 16

								flag = True

								for k in range(32):
									if k != 1 and buffer[num16 + k] != 0:
										flag = False

								if flag:
									if b != 2:
										flag2 = False
									break

								flag = True

								for l in range(16):
									if l != 1 and buffer[num16 + l] != 0:
										flag = False

								if (buffer[num16 + 1] == 2 or buffer[num16 + 1] == 3) and buffer[num16] == 12 and num5 >= 131072:
									flag = True

								if buffer[num16 + 1] == 4:
									flag2 = False
									flag = True
									b = 0
									flag9 = True

								if flag and not flag2:
									break

								if flag:
									if b == 1:
										num7 = num5
										b = 2
									elif b == 2:
										break
								
								if (num16 >= num - 128):
									if (stream.tell() >= length):
										flag = True
										break

									stream.seek(stream.tell() - 48)

									num16 = 0

									buffer[:] = stream.read(num2)
						
								num5 += 16
							
							num5 = stream.tell() - num2 + num16 - num8

							if (not flag and num5 <= 24576):
								continue
							
							if (num5 > 24576):
								ADPCMFile_ = ADPCMFile()
								ADPCMFile_.SourcePath = sFullPath

								if (flag2 and
									b == 2 and
									num7 <= 131072
								):

									ADPCMFile_.ADPCMType = ADPCMFile.ADPCM_TYPE.MIB
									ADPCMFile_.Interleave = 0
									ADPCMFile_.NbOfChannels = 2
									ADPCMFile_.SampleRate = 44100
									ADPCMFile_.StartOffset = num8
									ADPCMFile_.FileLength = num5 + num7

									if (ADPCMFile_.FileLength < 65536):
										stream.seek(num8 + num5 + num7 + 128)
										num16 = num
										break
								else:
									ADPCMFile_.ADPCMType = ADPCMFile.ADPCM_TYPE.PS2_INTERLEAVE
									ADPCMFile_.Interleave = 2000
									ADPCMFile_.NbOfChannels = 2
									ADPCMFile_.SampleRate = 44100

									if (flag9):
										num8 -= 1024
									
									ADPCMFile_.StartOffset = num8

									if (ADPCMFile_.StartOffset >= 16 and not flag9):
										stream.seek(ADPCMFile_.StartOffset - 16)

										if (int.from_bytes(stream.read(4)) == 0):
											ADPCMFile_.StartOffset += 16

									stream.seek(ADPCMFile_.StartOffset)

									stream.read(1)

									if (int.from_bytes(stream.read(1)) > 7):
										ADPCMFile_.StartOffset = num8
									
									if (flag9):
										ADPCMFile_.FileLength = num5 + 1024
									else:
										ADPCMFile_.FileLength = num5 + 32

								ADPCMFile_.TotalSamples = ADPCMFile_.FileLength / 16 * 28
								ADPCMFile_.FileName = ""
								stream.seek(num8 + ADPCMFile_.FileLength + 128)
								self.fileFound(ADPCMFile_)
								num16 = num
								break
							
							if (flag and num5 >= 16 and num16 != 0):
								num16 -= 16


					if (ADPCMFile_ == None):
						stream.seek(num6 - 128)
					else:
						stream.seek(stream.tell() - 128)

					## end
					if num == 0:
						break
			
			self.dump_file_table()
			ADPCMFile_ = None
			buffer = None
			stream.close()
			stream = None

if __name__ == "__main__":
	ripper = Ripper()
	ripper.CheckForInterleave = True

	if (len(sys.argv) < 2):
		print("Usage:")
		print("detect_audio_format.py <input>")

	ripper.RipFile(sys.argv[1])
