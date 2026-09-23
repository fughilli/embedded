# Build on the Raspberry Pi 5 (aarch64 Linux):
#   nix shell nixpkgs#gcc nixpkgs#gnumake -c make
CFLAGS ?= -O2 -Wall -Wextra -Wno-unused-parameter
CPPFLAGS += -Isrc -Ithird_party/cmsis-dap

SRCS = src/main.c src/rp1_gpio.c third_party/cmsis-dap/DAP.c \
       third_party/cmsis-dap/SW_DP.c third_party/cmsis-dap/DAP_vendor.c

swd_bridge: $(SRCS) $(wildcard src/*.h) third_party/cmsis-dap/DAP.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $(SRCS)

clean:
	rm -f swd_bridge

.PHONY: clean
