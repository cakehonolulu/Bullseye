#ifndef MENU_FILE_H
#define MENU_FILE_H

typedef struct Scroll {
    /* 0x00 */ s32 cur;
    /* 0x04 */ s32 from;
    /* 0x08 */ s32 to;
    /* 0x0C */ s32 state;
} Scroll;                      /* 0x10 */

typedef struct History {
    /* 0x00 */ s32 slot[19];
    /* 0x4C */ s32 top;
    /* 0x50 */ s32 bottom;
    /* 0x54 */ s32 count;
    /* 0x58 */ s32 unk58;
    /* 0x5C */ s32 locked;
} History;                   /* 0x60 */

typedef struct menu_file {
    /* 0x000 */ u8      unk000[0x2C];
    /* 0x02C */ s32     mode;
    /* 0x030 */ u8      unk030[0x83C];
    /* 0x86C */ u8      unk86C[0x2C];
    /* 0x898 */ u8      unk898[0x14];
    /* 0x8AC */ Scroll  scroll;
    /* 0x8BC */ u8      unk8BC[0x4];
    /* 0x8C0 */ History hist;
    /* 0x920 */ u8      unk920[0x8];
    /* 0x928 */ s32     sel;
} menu_file;

#endif /* MENU_FILE_H */
