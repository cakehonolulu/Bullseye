.section .text
.set noreorder

.macro move dest, src
    daddu \dest, \src, $0
.endm

FUN_00139408:
    addiu	$sp,$sp,-64
    lui	$v0,0x2e
    sd	$s2,32($sp)
    sd	$s1,16($sp)
    li	$s2,3
    sd	$s0,0($sp)
    sd	$ra,48($sp)
    addiu	$s0,$v0,11064
    lw	$a0,11064($v0)
    addiu	$s1,$s0,24
    jal	SetSyscall
    lw	$a1,4($s0)
    lui	$a1,0x2e
    lui	$a0,0x8007
    li	$a2,808
    addiu	$a1,$a1,10184
    jal	FUN_001393a0
    ori	$a0,$a0,0x5000
    jal	FlushCache
    move	$a0,$zero
    jal	FlushCache
    li	$a0,2
    lw	$a0,8($s0)
    jal	SetSyscall
    lw	$a1,12($s0)
    lw	$a0,16($s0)
    jal	SetSyscall
    lw	$a1,20($s0)
    lw	$a0,0($s1)
    nop
LAB_00139480:
    jal	RFU091_GetEntryAddress
    addiu	$s2,$s2,1
    lw	$a0,0($s1)
    move	$a1,$v0
    jal	SetSyscall
    addiu	$s1,$s1,8
    sltiu	$v0,$s2,8
    bnezl	$v0,LAB_00139480
    lw	$a0,0($s1)
    ld	$ra,48($sp)
    ld	$s2,32($sp)
    ld	$s1,16($sp)
    ld	$s0,0($sp)
    jr	$ra
    addiu	$sp,$sp,64
    nop
    