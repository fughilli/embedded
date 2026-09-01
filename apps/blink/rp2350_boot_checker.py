"""Assert the exact RP2350 arduino-pico blink image boots under the emulator.

With the //rules/sim/plugins/rp2350:rp2350_boot "basic set", the image boots from
its reset vector through the pico-sdk runtime_init and into clock init. This checks
it got there (bootrom-stubbed, from the real image), which is the current boot
milestone. Reaching setup()/loop() additionally needs the full CLOCKS/PLL model
(see the plugin's KNOWN LIMIT).
"""


def check(result):
    boot = result.by_name("rp2350.boot")
    assert boot is not None, "rp2350.boot plugin not in the device model"
    print("  boot milestones reached: %s" % boot.reached)
    for stage in ("runtime_init", "xosc_init", "pll_init"):
        assert stage in boot.reached, (
            "boot did not reach %s (got %s)" % (stage, boot.reached))
    assert not result.hit_budget, "boot stalled before the expected milestone"
