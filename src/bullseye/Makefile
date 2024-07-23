EE_BIN = bullseye.elf
EE_OBJS = entry.o
EE_LIBS = -ldebug -lc -nostartfiles -e entry

EE_OPTFLAGS = -O0
EE_WARNFLAGS = -Werror
EE_CXXFLAGS = -g3 -gdwarf-4 -gstrict-dwarf -Iinclude -Wno-strict-aliasing
EE_CFLAGS += -Iinclude

all: $(EE_BIN)

clean:
	rm -f *.o

include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal_cpp
