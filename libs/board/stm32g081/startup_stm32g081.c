/* Reset vector + interrupt vector table for the STM32G081 (Arm Cortex-M0+).
 *
 * Hand-written (no CubeG0 dependency) so the bare-metal firmware is fully
 * hermetic under Bazel + @arm_gcc. Reset_Handler initialises the C runtime
 * (.data copy, .bss zero, C++ ctors via __libc_init_array) and calls main().
 * The table's symbols/layout follow RM0444; every IRQ defaults to a spin loop
 * (Default_Handler) unless a strong definition overrides the weak alias.
 *
 * Symbols (_sidata, _sdata, _edata, _sbss, _ebss, _estack) come from
 * STM32G081xx.ld.
 */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;

extern int main(void);

/* Static-constructor tables emitted by the linker script (.preinit_array /
 * .init_array). We walk them directly rather than call newlib's
 * __libc_init_array(), which pulls in _init/_fini from crti/crtn — objects that
 * -nostartfiles omits (and whose v6-m _init trips a "dangerous relocation"). */
typedef void (*init_fn)(void);
extern init_fn __preinit_array_start[], __preinit_array_end[];
extern init_fn __init_array_start[], __init_array_end[];

void Reset_Handler(void);
void Default_Handler(void);

/* Copy .data from Flash to SRAM, zero .bss, run static constructors, main(). */
void Reset_Handler(void) {
  uint32_t *src = &_sidata;
  for (uint32_t *dst = &_sdata; dst < &_edata;) {
    *dst++ = *src++;
  }
  for (uint32_t *dst = &_sbss; dst < &_ebss;) {
    *dst++ = 0;
  }
  for (init_fn *fn = __preinit_array_start; fn < __preinit_array_end; ++fn) {
    (*fn)();
  }
  for (init_fn *fn = __init_array_start; fn < __init_array_end; ++fn) {
    (*fn)();
  }
  main();
  for (;;) {
  }
}

/* Weak default for every exception/IRQ: park the core so faults are catchable. */
void Default_Handler(void) {
  for (;;) {
  }
}

/* Core system exceptions + STM32G0x1 peripheral IRQs (RM0444). Each is a weak
 * alias of Default_Handler; define a strong symbol of the same name to hook it. */
#define ALIAS(name) __attribute__((weak, alias("Default_Handler"))) void name(void)

ALIAS(NMI_Handler);
ALIAS(HardFault_Handler);
ALIAS(SVC_Handler);
ALIAS(PendSV_Handler);
ALIAS(SysTick_Handler);

ALIAS(WWDG_IRQHandler);
ALIAS(PVD_IRQHandler);
ALIAS(RTC_TAMP_IRQHandler);
ALIAS(FLASH_IRQHandler);
ALIAS(RCC_IRQHandler);
ALIAS(EXTI0_1_IRQHandler);
ALIAS(EXTI2_3_IRQHandler);
ALIAS(EXTI4_15_IRQHandler);
ALIAS(UCPD1_2_IRQHandler);
ALIAS(DMA1_Channel1_IRQHandler);
ALIAS(DMA1_Channel2_3_IRQHandler);
ALIAS(DMA1_Ch4_7_DMAMUX1_OVR_IRQHandler);
ALIAS(ADC1_COMP_IRQHandler);
ALIAS(TIM1_BRK_UP_TRG_COM_IRQHandler);
ALIAS(TIM1_CC_IRQHandler);
ALIAS(TIM2_IRQHandler);
ALIAS(TIM3_IRQHandler);
ALIAS(TIM6_DAC_LPTIM1_IRQHandler);
ALIAS(TIM7_LPTIM2_IRQHandler);
ALIAS(TIM14_IRQHandler);
ALIAS(TIM15_IRQHandler);
ALIAS(TIM16_IRQHandler);
ALIAS(TIM17_IRQHandler);
ALIAS(I2C1_IRQHandler);
ALIAS(I2C2_IRQHandler);
ALIAS(SPI1_IRQHandler);
ALIAS(SPI2_IRQHandler);
ALIAS(USART1_IRQHandler);
ALIAS(USART2_IRQHandler);
ALIAS(USART3_4_LPUART1_IRQHandler);
ALIAS(CEC_IRQHandler);
ALIAS(AES_RNG_IRQHandler);

/* The vector table: initial SP, reset vector, system exceptions, then the 32
 * maskable IRQs. Placed at 0x08000000 by the .isr_vector section. */
__attribute__((section(".isr_vector"), used))
void (*const g_pfnVectors[])(void) = {
    (void (*)(void))(&_estack),  /* 0x00 initial stack pointer */
    Reset_Handler,               /* 0x04 reset */
    NMI_Handler,                 /* 0x08 */
    HardFault_Handler,           /* 0x0C */
    0, 0, 0, 0, 0, 0, 0,         /* reserved */
    SVC_Handler,                 /* 0x2C */
    0, 0,                        /* reserved */
    PendSV_Handler,              /* 0x38 */
    SysTick_Handler,             /* 0x3C */

    WWDG_IRQHandler,                        /* 0 */
    PVD_IRQHandler,                         /* 1 */
    RTC_TAMP_IRQHandler,                    /* 2 */
    FLASH_IRQHandler,                       /* 3 */
    RCC_IRQHandler,                         /* 4 */
    EXTI0_1_IRQHandler,                     /* 5 */
    EXTI2_3_IRQHandler,                     /* 6 */
    EXTI4_15_IRQHandler,                    /* 7 */
    UCPD1_2_IRQHandler,                     /* 8 */
    DMA1_Channel1_IRQHandler,               /* 9 */
    DMA1_Channel2_3_IRQHandler,             /* 10 */
    DMA1_Ch4_7_DMAMUX1_OVR_IRQHandler,      /* 11 */
    ADC1_COMP_IRQHandler,                   /* 12 */
    TIM1_BRK_UP_TRG_COM_IRQHandler,         /* 13 */
    TIM1_CC_IRQHandler,                     /* 14 */
    TIM2_IRQHandler,                        /* 15 */
    TIM3_IRQHandler,                        /* 16 */
    TIM6_DAC_LPTIM1_IRQHandler,             /* 17 */
    TIM7_LPTIM2_IRQHandler,                 /* 18 */
    TIM14_IRQHandler,                       /* 19 */
    TIM15_IRQHandler,                       /* 20 */
    TIM16_IRQHandler,                       /* 21 */
    TIM17_IRQHandler,                       /* 22 */
    I2C1_IRQHandler,                        /* 23 */
    I2C2_IRQHandler,                        /* 24 */
    SPI1_IRQHandler,                        /* 25 */
    SPI2_IRQHandler,                        /* 26 */
    USART1_IRQHandler,                      /* 27 */
    USART2_IRQHandler,                      /* 28 */
    USART3_4_LPUART1_IRQHandler,            /* 29 */
    CEC_IRQHandler,                         /* 30 */
    AES_RNG_IRQHandler,                     /* 31 */
};
