#ifndef MACROS_H
#define MACROS_H

/*
 * INCLUDE_ASM lets a translation unit be partially decompiled: functions
 * you've written in C sit next to raw assembly for the ones you haven't,
 * and the object file still links. This is the single biggest reason to
 * target GCC rather than MWCC for a matching build.
 *
 *   INCLUDE_ASM("asm/nonmatchings/foo", func_00138E08);
 */
#define INCLUDE_ASM(FOLDER, NAME)                     \
    __asm__(                                          \
        ".section .text\n"                            \
        "\t.align\t3\n"                               \
        "\t.globl\t" #NAME "\n"                       \
        "\t.type\t" #NAME ", @function\n"             \
        "\t.ent\t" #NAME "\n"                         \
        #NAME ":\n"                                   \
        "\t.include \"" FOLDER "/" #NAME ".s\"\n"     \
        "\t.end\t" #NAME "\n")

#define INCLUDE_RODATA(FOLDER, NAME)                  \
    __asm__(                                          \
        ".section .rodata\n"                          \
        "\t.align\t3\n"                               \
        #NAME ":\n"                                   \
        "\t.include \"" FOLDER "/" #NAME ".s\"\n")

/* EE-specific glue that shows up constantly in R5900 code. */
#ifndef ALIGNED
#define ALIGNED(x) __attribute__((aligned(x)))
#endif

#endif /* MACROS_H */
