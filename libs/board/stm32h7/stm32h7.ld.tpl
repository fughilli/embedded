/* Minimal GNU ld script for the STM32H7 (Arm Cortex-M7).
 *
 * TEMPLATE: @FLASH_K@ / @RAM_K@ are substituted per part by the
 * `stm32h7_linker_script` macro (//libs/board/stm32h7:stm32h7.bzl). Single-M7
 * view of the STM32H757: Flash at 0x08000000 (2MB dual-bank), and code+data in
 * the D1-domain AXI-SRAM at 0x24000000 (512K) — a large, contiguous, M7-fast
 * region well-suited for a benchmark. (DTCM at 0x20000000 exists too but is left
 * for a later fidelity split; AXI-SRAM keeps this simple and roomy.) The vector
 * table lives at the start of Flash; the reset vector points at Reset_Handler
 * (see startup_stm32h7.c), and the initial stack pointer is the top of RAM.
 * Sections are placed so Reset_Handler can copy .data from Flash (_sidata) to RAM
 * (_sdata.._edata) and zero .bss (_sbss.._ebss). --gc-sections drops unused.
 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = @FLASH_K@K
    RAM   (rwx) : ORIGIN = 0x24000000, LENGTH = @RAM_K@K
}

/* Top of stack = end of RAM (full-descending stack). */
_estack = ORIGIN(RAM) + LENGTH(RAM);

/* Reserve space so a naive stack overflow trips the linker, not silent SRAM. */
_Min_Heap_Size  = 0x200;
_Min_Stack_Size = 0x400;

SECTIONS
{
    /* Interrupt vector table first, then code + read-only data in Flash. */
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } > FLASH

    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.glue_7)
        *(.glue_7t)
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    .rodata :
    {
        . = ALIGN(4);
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
    .ARM :
    {
        __exidx_start = .;
        *(.ARM.exidx*)
        __exidx_end = .;
    } > FLASH

    /* C++ static constructors (run by Reset_Handler). */
    .preinit_array :
    {
        PROVIDE_HIDDEN(__preinit_array_start = .);
        KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } > FLASH
    .init_array :
    {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } > FLASH
    .fini_array :
    {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > FLASH

    /* .data: initialised RAM, loaded (LMA) from Flash, copied at startup. */
    _sidata = LOADADDR(.data);
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH

    /* .bss: zero-initialised RAM, cleared at startup. */
    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } > RAM

    /* Guard region: fail the link if heap+stack won't fit in the remaining RAM. */
    ._user_heap_stack :
    {
        . = ALIGN(8);
        PROVIDE(end = .);
        PROVIDE(_end = .);
        . = . + _Min_Heap_Size;
        . = . + _Min_Stack_Size;
        . = ALIGN(8);
    } > RAM

    .ARM.attributes 0 : { *(.ARM.attributes) }
}
