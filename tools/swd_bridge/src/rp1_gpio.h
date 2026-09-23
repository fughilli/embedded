// Direct register access to the Raspberry Pi 5 RP1 GPIO block (bank 0, header GPIO0-27)
// through /dev/gpiomem0, for bit-banging SWD without a syscall per edge.
//
// Register layout from raspberrypi/utils pinctrl/gpiochip_rp1.c:
//   IO_BANK0  +0x00000  per pin: STATUS (+8n), CTRL (+8n+4), FUNCSEL in CTRL[4:0]
//   SYS_RIO0  +0x10000  OUT (+0x0), OE (+0x4), SYNC_IN (+0x8); SET alias +0x2000, CLR alias +0x3000
//   PADS0     +0x20000  per pin: +4+4n; OD bit 7, IE bit 6, PUE bit 3, PDE bit 2
#ifndef SWD_BRIDGE_RP1_GPIO_H_
#define SWD_BRIDGE_RP1_GPIO_H_

#include <stdint.h>

#define RP1_IO_BANK0 0x00000u
#define RP1_SYS_RIO0 0x10000u
#define RP1_PADS0 0x20000u
#define RP1_MAP_SIZE 0x30000u

#define RP1_SET 0x2000u
#define RP1_CLR 0x3000u

#define RP1_RIO_OUT 0x0u
#define RP1_RIO_OE 0x4u
#define RP1_RIO_SYNC_IN 0x8u

#define RP1_FSEL_MASK 0x1fu
#define RP1_FSEL_SYS_RIO 5u
#define RP1_CTRL_OVERRIDES (0xfu << 12)  // OUTOVER[13:12], OEOVER[15:14]

#define RP1_PAD_OD (1u << 7)
#define RP1_PAD_IE (1u << 6)
#define RP1_PAD_PUE (1u << 3)
#define RP1_PAD_PDE (1u << 2)

extern volatile uint32_t *rp1_base;

static inline volatile uint32_t *rp1_reg(uint32_t offset) {
  return rp1_base + offset / 4;
}

// Posted PCIe writes to RP1 can reach the pins back to back; a read-back forces the
// preceding write to land before we time the next edge.
static inline void rp1_flush(void) {
  (void)*rp1_reg(RP1_SYS_RIO0 + RP1_RIO_SYNC_IN);
}

static inline void rp1_out_set(uint32_t mask) {
  *rp1_reg(RP1_SYS_RIO0 + RP1_SET + RP1_RIO_OUT) = mask;
}

static inline void rp1_out_clr(uint32_t mask) {
  *rp1_reg(RP1_SYS_RIO0 + RP1_CLR + RP1_RIO_OUT) = mask;
}

static inline void rp1_oe_set(uint32_t mask) {
  *rp1_reg(RP1_SYS_RIO0 + RP1_SET + RP1_RIO_OE) = mask;
}

static inline void rp1_oe_clr(uint32_t mask) {
  *rp1_reg(RP1_SYS_RIO0 + RP1_CLR + RP1_RIO_OE) = mask;
}

static inline uint32_t rp1_in(void) {
  return *rp1_reg(RP1_SYS_RIO0 + RP1_RIO_SYNC_IN);
}

// Map /dev/gpiomem0. Returns 0 on success.
int rp1_open(void);

// Hand a pin to SYS_RIO as a high-Z input, with the given pull (PUE/PDE bits, or 0).
// The previous CTRL/PADS values are saved and put back by rp1_restore_all().
void rp1_claim(unsigned pin, uint32_t pull);

void rp1_restore_all(void);

#endif  // SWD_BRIDGE_RP1_GPIO_H_
