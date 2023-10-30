#include <bullseye.h>
#include <stdbool.h>
#include <stdint.h>

void entry(void)
{
	uint32_t src = 0x0031d300;

	volatile uint32_t *ptr = (uint32_t *) src;

    while (src < 0x004d04ac) {
        *ptr = 0;
        src += 4;
        ptr++;
    }

    printf("Hello from Bullseye!\n");



    while (1) {};

}
