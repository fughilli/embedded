// CMSIS-DAP board configuration for SWD bit-banged from Raspberry Pi 5 GPIO (RP1).
//
// Pins are chosen at runtime (see main.c); defaults GPIO25 = SWCLK, GPIO24 = SWDIO.
// Timing: CPU_CLOCK is declared as 1 GHz with one "cycle" per delay iteration, so the
// clock_delay DAP.c derives from DAP_SWJ_Clock is directly the half period in ns, and
// PIN_DELAY_SLOW busy-waits that many ns. Each SWCLK edge also waits for its posted
// write to reach RP1 (~1 us), which caps the real clock at a few hundred kHz.
#ifndef __DAP_CONFIG_H__
#define __DAP_CONFIG_H__

#include <stdint.h>
#include <string.h>
#include <time.h>

#include "cmsis_compiler.h"
#include "rp1_gpio.h"

#define CPU_CLOCK 1000000000U
#define IO_PORT_WRITE_CYCLES 1U
#define DELAY_SLOW_CYCLES 1U

#define DAP_SWD 1
#define DAP_JTAG 0
#define DAP_JTAG_DEV_CNT 1U
#define DAP_DEFAULT_PORT 1U
#define DAP_DEFAULT_SWJ_CLOCK 1000000U

// One command in flight over TCP; large packets amortize the network round trip.
#define DAP_PACKET_SIZE 1024U
#define DAP_PACKET_COUNT 1U

#define SWO_UART 0
#define SWO_UART_DRIVER 0
#define SWO_UART_MAX_BAUDRATE 0U
#define SWO_MANCHESTER 0
#define SWO_BUFFER_SIZE 4096U
#define SWO_STREAM 0
#define TIMESTAMP_CLOCK 0U
#define DAP_UART 0
#define DAP_UART_DRIVER 0
#define DAP_UART_RX_BUFFER_SIZE 1024U
#define DAP_UART_TX_BUFFER_SIZE 1024U
#define DAP_UART_USB_COM_PORT 0
#define TARGET_FIXED 0

// Runtime pin selection (main.c).
extern uint32_t swd_clk_mask;
extern uint32_t swd_dio_mask;
extern uint32_t swd_nreset_mask;  // 0 when no reset line is wired
extern char swd_serial[64];

static inline uint64_t swd_now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}

#define DAP_PIN_DELAY_SLOW_PROVIDED 1
__STATIC_FORCEINLINE void PIN_DELAY_SLOW(uint32_t delay_ns) {
  if (delay_ns < 100U) return;  // below the cost of one RP1 access anyway
  uint64_t end = swd_now_ns() + delay_ns;
  while (swd_now_ns() < end) {
  }
}

static inline uint8_t swd_copy_str(char *dst, const char *src) {
  size_t n = strlen(src) + 1;
  memcpy(dst, src, n);
  return (uint8_t)n;
}

__STATIC_INLINE uint8_t DAP_GetVendorString(char *str) { return swd_copy_str(str, "swd_bridge"); }
__STATIC_INLINE uint8_t DAP_GetProductString(char *str) {
  return swd_copy_str(str, "RPi5 GPIO SWD (elaphureLink)");
}
__STATIC_INLINE uint8_t DAP_GetSerNumString(char *str) { return swd_copy_str(str, swd_serial); }
__STATIC_INLINE uint8_t DAP_GetTargetDeviceVendorString(char *str) { (void)str; return 0U; }
__STATIC_INLINE uint8_t DAP_GetTargetDeviceNameString(char *str) { (void)str; return 0U; }
__STATIC_INLINE uint8_t DAP_GetTargetBoardVendorString(char *str) { (void)str; return 0U; }
__STATIC_INLINE uint8_t DAP_GetTargetBoardNameString(char *str) { (void)str; return 0U; }
__STATIC_INLINE uint8_t DAP_GetProductFirmwareVersionString(char *str) { (void)str; return 0U; }

// Port setup ---------------------------------------------------------------

__STATIC_INLINE void PORT_JTAG_SETUP(void) {}

// SWCLK and SWDIO driven high; nRESET released.
__STATIC_INLINE void PORT_SWD_SETUP(void) {
  rp1_out_set(swd_clk_mask | swd_dio_mask);
  rp1_oe_set(swd_clk_mask | swd_dio_mask);
  if (swd_nreset_mask) rp1_oe_clr(swd_nreset_mask);
  rp1_flush();
}

// Everything high-Z, so the target is left alone between sessions.
__STATIC_INLINE void PORT_OFF(void) {
  rp1_oe_clr(swd_clk_mask | swd_dio_mask | swd_nreset_mask);
  rp1_flush();
}

// SWCLK --------------------------------------------------------------------

__STATIC_FORCEINLINE uint32_t PIN_SWCLK_TCK_IN(void) { return (rp1_in() & swd_clk_mask) ? 1U : 0U; }

__STATIC_FORCEINLINE void PIN_SWCLK_TCK_SET(void) {
  rp1_out_set(swd_clk_mask);
  rp1_flush();
}

__STATIC_FORCEINLINE void PIN_SWCLK_TCK_CLR(void) {
  rp1_out_clr(swd_clk_mask);
  rp1_flush();
}

// SWDIO (data writes are ordered ahead of the next SWCLK edge, which flushes) -

__STATIC_FORCEINLINE uint32_t PIN_SWDIO_TMS_IN(void) { return (rp1_in() & swd_dio_mask) ? 1U : 0U; }
__STATIC_FORCEINLINE void PIN_SWDIO_TMS_SET(void) { rp1_out_set(swd_dio_mask); }
__STATIC_FORCEINLINE void PIN_SWDIO_TMS_CLR(void) { rp1_out_clr(swd_dio_mask); }
__STATIC_FORCEINLINE uint32_t PIN_SWDIO_IN(void) { return (rp1_in() & swd_dio_mask) ? 1U : 0U; }

__STATIC_FORCEINLINE void PIN_SWDIO_OUT(uint32_t bit) {
  if (bit & 1U) {
    rp1_out_set(swd_dio_mask);
  } else {
    rp1_out_clr(swd_dio_mask);
  }
}

__STATIC_FORCEINLINE void PIN_SWDIO_OUT_ENABLE(void) { rp1_oe_set(swd_dio_mask); }

// Released SWDIO is held high by the pad pull-up (and the target's).
__STATIC_FORCEINLINE void PIN_SWDIO_OUT_DISABLE(void) {
  rp1_oe_clr(swd_dio_mask);
  rp1_flush();
}

// JTAG-only pins: not wired -------------------------------------------------

__STATIC_FORCEINLINE uint32_t PIN_TDI_IN(void) { return 0U; }
__STATIC_FORCEINLINE void PIN_TDI_OUT(uint32_t bit) { (void)bit; }
__STATIC_FORCEINLINE uint32_t PIN_TDO_IN(void) { return 0U; }
__STATIC_FORCEINLINE uint32_t PIN_nTRST_IN(void) { return 0U; }
__STATIC_FORCEINLINE void PIN_nTRST_OUT(uint32_t bit) { (void)bit; }

// nRESET: optional, open-drain emulated (drive low, or release to the pull-up) --

__STATIC_FORCEINLINE uint32_t PIN_nRESET_IN(void) {
  if (!swd_nreset_mask) return 1U;
  return (rp1_in() & swd_nreset_mask) ? 1U : 0U;
}

__STATIC_FORCEINLINE void PIN_nRESET_OUT(uint32_t bit) {
  if (!swd_nreset_mask) return;
  if (bit & 1U) {
    rp1_oe_clr(swd_nreset_mask);
  } else {
    rp1_out_clr(swd_nreset_mask);
    rp1_oe_set(swd_nreset_mask);
  }
  rp1_flush();
}

// Misc ---------------------------------------------------------------------

__STATIC_INLINE void LED_CONNECTED_OUT(uint32_t bit) { (void)bit; }
__STATIC_INLINE void LED_RUNNING_OUT(uint32_t bit) { (void)bit; }
__STATIC_INLINE uint32_t TIMESTAMP_GET(void) { return 0U; }

// Pins are claimed in main() before DAP_Setup(); start released.
__STATIC_INLINE void DAP_SETUP(void) { PORT_OFF(); }

__STATIC_INLINE uint8_t RESET_TARGET(void) { return 0U; }

#endif  // __DAP_CONFIG_H__
