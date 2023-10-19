.section .text
.global entry

.set noreorder

.macro move dest, src
    daddu \dest, \src, $0
.endm

entry:
	lui $v0, 0x32
	lui $v1, 0x4d
	addiu $v0, $v0, -11520
	addiu $v1, $v1, 1196
LAB_00100018:
	sq $zero, 0($v0)
	nop
	sltu $at, $v0, $v1
	nop
	nop
	bnez $at, LAB_00100018
	addiu $v0, $v0, 16
	lui $a0, 0x32
	lui $a1, 0x54
	lui $a2, 0x4
	lui $a3, 0x32
	lui $t0, 0x10
	addiu $a0, $a0, 6128
	addiu $a1, $a1, 0
	addiu $a2, $a2, 0
	addiu $a3, $a3, -10880
	addiu $t0, $t0, 192
	move $gp, $a0
	li $v1, 60
	syscall
	move $sp, $v0
	lui $a0, 0x4d
	lui $a1, 0x0
	addiu $a0, $a0, 1196
	addiu $a1, $a1, -1
	li $v1, 61
	syscall
	jal 0x138e08
	nop
	jal 0x130ea0
	move $a0, $zero
	ei
	lui $v0, 0x32
	addiu $v0, $v0, -10880
	lw $a0, 0($v0)
	jal 0x16af7c
	addiu $a1, $v0, 4
	j 0x139078
	move $a0, $v0
	nop
