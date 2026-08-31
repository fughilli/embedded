// STM32G081 board support: drive the on-board LED with bare register access
// (no Arduino/HAL). Target is the NUCLEO-G081RB, whose green user LED (LD4) is
// on PA5. Register addresses/bitfields are from RM0444.
#include <stdint.h>

#include "libs/board/stm32g081/stm32g081.h"

// --- Minimal register map (RM0444) -----------------------------------------
#define RCC_BASE 0x40021000u
#define GPIOA_BASE 0x50000000u

#define MMIO32(addr) (*(volatile uint32_t *)(addr))

// RCC I/O port clock enable register; bit 0 = GPIOAEN.
#define RCC_IOPENR MMIO32(RCC_BASE + 0x34u)
#define RCC_IOPENR_GPIOAEN (1u << 0)

// GPIOA registers.
#define GPIOA_MODER MMIO32(GPIOA_BASE + 0x00u)
#define GPIOA_BSRR MMIO32(GPIOA_BASE + 0x18u)

#define LED_PIN 5u  // PA5 = NUCLEO-G081RB LD4

void board_setup(void) {
  // Enable the GPIOA peripheral clock, then wait for it to take effect.
  RCC_IOPENR |= RCC_IOPENR_GPIOAEN;
  (void)RCC_IOPENR;

  // MODER: 2 bits/pin. Clear PA5's field, then set 0b01 = general-purpose output.
  GPIOA_MODER &= ~(0x3u << (LED_PIN * 2));
  GPIOA_MODER |= (0x1u << (LED_PIN * 2));
}

void board_set_led(bool on) {
  // BSRR: writing bit n sets the pin, bit n+16 resets it (atomic, no RMW).
  GPIOA_BSRR = on ? (1u << LED_PIN) : (1u << (LED_PIN + 16));
}

void board_delay_ms(unsigned ms) {
  // ~16 MHz core; the inner loop is a few cycles per iteration. Approximate.
  for (unsigned i = 0; i < ms; ++i) {
    for (volatile unsigned c = 0; c < 4000; ++c) {
    }
  }
}
