#include "rp1_gpio.h"

#include <fcntl.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

volatile uint32_t *rp1_base;

#define MAX_CLAIMED 4

static struct {
  unsigned pin;
  uint32_t ctrl;
  uint32_t pad;
} claimed[MAX_CLAIMED];
static unsigned n_claimed;

static uint32_t ctrl_off(unsigned pin) { return RP1_IO_BANK0 + 8u * pin + 4u; }
static uint32_t pad_off(unsigned pin) { return RP1_PADS0 + 4u + 4u * pin; }

int rp1_open(void) {
  int fd = open("/dev/gpiomem0", O_RDWR | O_SYNC);
  if (fd < 0) {
    perror("open /dev/gpiomem0 (is this a Raspberry Pi 5?)");
    return -1;
  }
  void *p = mmap(NULL, RP1_MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  close(fd);
  if (p == MAP_FAILED) {
    perror("mmap /dev/gpiomem0");
    return -1;
  }
  rp1_base = p;
  return 0;
}

void rp1_claim(unsigned pin, uint32_t pull) {
  if (n_claimed < MAX_CLAIMED) {
    claimed[n_claimed].pin = pin;
    claimed[n_claimed].ctrl = *rp1_reg(ctrl_off(pin));
    claimed[n_claimed].pad = *rp1_reg(pad_off(pin));
    n_claimed++;
  }
  uint32_t mask = 1u << pin;
  rp1_oe_clr(mask);
  *rp1_reg(pad_off(pin)) =
      (*rp1_reg(pad_off(pin)) & ~(RP1_PAD_OD | RP1_PAD_PUE | RP1_PAD_PDE)) | RP1_PAD_IE | pull;
  *rp1_reg(ctrl_off(pin)) =
      (*rp1_reg(ctrl_off(pin)) & ~(RP1_FSEL_MASK | RP1_CTRL_OVERRIDES)) | RP1_FSEL_SYS_RIO;
  rp1_flush();
}

void rp1_restore_all(void) {
  if (!rp1_base) return;
  while (n_claimed) {
    n_claimed--;
    unsigned pin = claimed[n_claimed].pin;
    rp1_oe_clr(1u << pin);
    *rp1_reg(pad_off(pin)) = claimed[n_claimed].pad;
    *rp1_reg(ctrl_off(pin)) = claimed[n_claimed].ctrl;
  }
  rp1_flush();
}
