"""Rewrite an SDK sections.ld so `.ext_ram.bss` lands in PSRAM.

The prebuilt esp32-arduino-libs were linked with CONFIG_SPIRAM_ALLOW_BSS_SEG_
EXTERNAL_MEMORY off, so their ldgen-generated sections.ld folds `.ext_ram.bss`
(EXT_RAM_BSS_ATTR) into internal `.dram0.bss`. With the option on in the sdkconfig
overlay and esp_psram rebuilt from source (which reserves the section out of the PSRAM
heap and zeroes it at boot), the section has to be its own output section in PSRAM,
bracketed by `_ext_ram_bss_start` / `_ext_ram_bss_end`, as IDF's
components/esp_system/ld/<chip>/sections.ld.in places it.

    ext_ram_bss.py <sdk sections.ld> <out sections.ld>
"""

import re
import sys

INPUT = "*(.ext_ram.bss .ext_ram.bss.*)"

SECTION = """
  /* .ext_ram.bss in PSRAM (CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY; placed as IDF's
   * sections.ld.in does; written by @embedded//ld:ext_ram_bss.py). */
  .ext_ram.bss (NOLOAD) :
  {
    _ext_ram_bss_start = ABSOLUTE(.);
    *(.ext_ram.bss .ext_ram.bss.*)
    . = ALIGN(4);
    _ext_ram_bss_end = ABSOLUTE(.);
  } > ext_ram_seg
"""


def rewrite(text: str) -> str:
    if "_ext_ram_bss_start" in text:
        raise SystemExit("ext_ram_bss.py: the input already places .ext_ram.bss")
    n = text.count(INPUT)
    if n != 1:
        raise SystemExit(f"ext_ram_bss.py: expected one {INPUT} in .dram0.bss, found {n}")
    text = text.replace(INPUT, "/* .ext_ram.bss: in PSRAM (.ext_ram.bss below) */", 1)
    # After the internal heap-start marker section, which closes the DRAM layout.
    m = re.search(r"\.dram0\.heap_start \(NOLOAD\) :\s*\{[^}]*\}\s*>\s*sram_seg\n", text)
    if not m:
        raise SystemExit("ext_ram_bss.py: no .dram0.heap_start section to place it after")
    return text[: m.end()] + SECTION + text[m.end() :]


def main() -> None:
    src, out = sys.argv[1], sys.argv[2]
    with open(src) as f:
        text = f.read()
    with open(out, "w") as f:
        f.write(rewrite(text))


if __name__ == "__main__":
    main()
