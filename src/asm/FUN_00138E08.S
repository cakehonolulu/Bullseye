.section .text
.set noreorder

FUN_00138E08:
	addiu $sp, -0x10
	sd $ra, 0($sp)
	jal FUN_00138D08
	nop
	jal FUN_00138D98
	nop
	jal FUN_00131988
	nop
	jal FUN_00131B38
	nop
	jal FUN_00138F18
	nop
	ld $ra, 0($sp)
	j FUN_00139408
	addiu $sp, 0x10
	nop
