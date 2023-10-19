#include <stdbool.h>

typedef void (*FunctionPtr)();

void entry(void)
{
	FunctionPtr functionPtr;

	functionPtr = (FunctionPtr)0x00138d08;

	functionPtr();

	bool bVar1;
	unsigned int in_zero_lo;
	unsigned int in_zero_hi;
	unsigned int in_zero_udw;
	unsigned int in_register_0000000c;
	unsigned long long *puVar2;
	unsigned long long uVar3;

	puVar2 = (unsigned int *) 0x0031d300;
	do {
		*(unsigned long long *)puVar2 = 0;
		bVar1 = puVar2 < (unsigned int *) 0x004d04ac;
		puVar2 = puVar2 + 2;
	} while (bVar1);

	return;
}