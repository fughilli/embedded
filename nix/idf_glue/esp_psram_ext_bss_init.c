// .ext_ram.bss zeroing for an SDK whose startup was prebuilt WITHOUT
// CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY: its cpu_start.c calls
// esp_psram_bss_init() only when built with the option, so with the option on in the
// sdkconfig overlay (and esp_psram rebuilt from source, which keeps the section out of
// the PSRAM heap) nothing would zero it. A CORE init function runs after cpu_start has
// mapped PSRAM and before init_heap (100) and the global constructors.
#include "sdkconfig.h"
#include "esp_bit_defs.h"
#include "esp_err.h"
#include "esp_private/startup_internal.h"
#include "esp_private/esp_psram_extram.h"

#if CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY
ESP_SYSTEM_INIT_FN(esp_psram_ext_bss_zero, CORE, BIT(0), 99)
{
    esp_psram_bss_init();
    return ESP_OK;
}
#endif
