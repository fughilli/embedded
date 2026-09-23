Vendored from https://github.com/ARM-software/CMSIS-DAP at 12636590eec66fae2d1bba4518749426ad5a4595 (Apache-2.0, see LICENSE):
Firmware/Source/{DAP.c,SW_DP.c,DAP_vendor.c}, Firmware/Include/DAP.h.

Local change (DAP.h): `PIN_DELAY_SLOW` is skipped when `DAP_PIN_DELAY_SLOW_PROVIDED` is
defined, so a host build can supply its own delay (the upstream one is Thumb assembly).
