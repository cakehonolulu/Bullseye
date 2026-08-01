#ifndef COMMON_H
#define COMMON_H

#include "include_asm.h"

typedef signed char        s8;
typedef unsigned char      u8;
typedef signed short       s16;
typedef unsigned short     u16;
typedef signed int         s32;
typedef unsigned int       u32;
typedef signed long long   s64;
typedef unsigned long long u64;
typedef float              f32;
typedef double             f64;

#ifndef u128
typedef unsigned int u128 __attribute__((mode(TI)));
#endif

#define NULL 0

#include "menu_file.h"
#include "ckzgunadjust.h"
#include "functions.h"

#endif /* COMMON_H */
