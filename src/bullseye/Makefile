EE_BIN = bullseye.elf

EE_OBJS = entry.o
EE_CFLAGS += -fdata-sections -ffunction-sections -Iinclude -g3 -gdwarf-4 -gstrict-dwarf -Iinclude -Wno-strict-aliasing
EE_LDFLAGS += -Wl,--gc-sections
EE_LIBS += -ldebug -lc

ifeq ($(DUMMY_TIMEZONE), 1)
   EE_CFLAGS += -DDUMMY_TIMEZONE
endif

ifeq ($(DUMMY_LIBC_INIT), 1)
   EE_CFLAGS += -DDUMMY_LIBC_INIT
endif

ifeq ($(KERNEL_NOPATCH), 1)
   EE_CFLAGS += -DKERNEL_NOPATCH
endif

ifeq ($(DEBUG), 1)
  EE_CFLAGS += -DDEBUG -O0 -g
else 
  EE_CFLAGS += -Os
  EE_LDFLAGS += -s
endif

all: $(EE_BIN)

clean:
	rm -rf $(EE_OBJS) $(EE_BIN)

# Include makefiles
include $(PS2SDK)/samples/Makefile.pref
include $(PS2SDK)/samples/Makefile.eeglobal