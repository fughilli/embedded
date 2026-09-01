// STM32G0 board support: drive the LED with bare register access (no Arduino/
// HAL). Wired for an LED on PD8. Register addresses/bitfields are from RM0444 and
// are identical across the G0 family; port D + pin 8 need a G0 part/package that
// bonds out PD8 (e.g. the STM32G0B1).
//
// To move the LED, change the three LED_* defines below: the port's base address
// and its RCC IOPENR clock-enable bit (GPIOxEN = bit x: A=0,B=1,C=2,D=3,E=4,F=5),
// plus the pin number.
#include <stdint.h>

#include "libs/board/stm32g0/stm32g0.h"

// --- Minimal register map (RM0444) -----------------------------------------
#define RCC_BASE 0x40021000u
// GPIO ports are 0x400 apart: A=0x50000000, B=..0400, C=..0800, D=..0C00, ...
#define GPIOD_BASE 0x50000C00u

#define MMIO32(addr) (*(volatile uint32_t *)(addr))

// RCC I/O port clock enable register.
#define RCC_IOPENR MMIO32(RCC_BASE + 0x34u)

// --- LED wiring: PD8 -------------------------------------------------------
#define LED_GPIO_BASE GPIOD_BASE
#define LED_IOPEN_BIT 3u  // GPIODEN = RCC_IOPENR bit 3
#define LED_PIN 8u

// GPIO port registers (MODER at +0x00, BSRR at +0x18) for the LED's port.
#define LED_MODER MMIO32(LED_GPIO_BASE + 0x00u)
#define LED_BSRR MMIO32(LED_GPIO_BASE + 0x18u)

void board_setup(void) {
  // Enable the LED port's peripheral clock, then wait for it to take effect.
  RCC_IOPENR |= (1u << LED_IOPEN_BIT);
  (void)RCC_IOPENR;

  // MODER: 2 bits/pin. Clear the pin's field, then set 0b01 = output.
  LED_MODER &= ~(0x3u << (LED_PIN * 2));
  LED_MODER |= (0x1u << (LED_PIN * 2));
}

void board_set_led(bool on) {
  // BSRR: writing bit n sets the pin, bit n+16 resets it (atomic, no RMW).
  LED_BSRR = on ? (1u << LED_PIN) : (1u << (LED_PIN + 16));
}

void board_delay_ms(unsigned ms) {
  // ~16 MHz core; the inner loop is a few cycles per iteration. Approximate.
  for (unsigned i = 0; i < ms; ++i) {
    for (volatile unsigned c = 0; c < 4000; ++c) {
    }
  }
}
