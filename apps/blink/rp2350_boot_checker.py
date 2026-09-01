"""Assert the exact RP2350 arduino-pico blink image boots to loop() and blinks.

With the //rules/sim/plugins/rp2350:rp2350_boot model, the exact flashed image
boots from its reset vector through the pico-sdk runtime_init, into main/setup/loop,
and toggles the on-board LED (GPIO25) via the GPIO coprocessor.
"""


def check(result):
    boot = result.by_name("rp2350.boot")
    assert boot is not None, "rp2350.boot plugin not in the device model"
    print("  boot milestones: %s" % boot.reached)
    print("  LED (GPIO25) transitions: %s" % boot.transitions)
    for stage in ("runtime_init", "pll_init", "main", "setup", "loop"):
        assert stage in boot.reached, "boot did not reach %s (got %s)" % (stage, boot.reached)
    t = boot.transitions
    assert len(t) >= 4, "LED toggled only %d times; expected a blink" % len(t)
    for i in range(1, len(t)):
        assert t[i] != t[i - 1], "LED did not alternate: %s" % t
