.section .text
.set noreorder

.macro move dest, src
    daddu \dest, \src, $0
.endm

main:
	addiu $sp,$sp,-32
	sd $s0,0($sp)
	move $s0,$a0
	sd $s1,8($sp)
	sd $ra,16($sp)
	jal	0x121268
	move $s1,$a1
	move $a1,$s1
	jal	0x1d2c18
	move $a0,$s0
	jal	0x15d4f4
	li $a0,53
	jal	0x16af58
	lui	$s0,0x29
	jal	0x1d3128
	nop
LAB_0016afbc:
	addiu $s0,$s0,19600
	jal	0x185f44
	move $a0,$s0
	jal	0x185ff4
	move $a0,$s0
	jal	0x1860b0
	move $a0,$s0
	b LAB_0016afbc
	lui	$s0,0x29
