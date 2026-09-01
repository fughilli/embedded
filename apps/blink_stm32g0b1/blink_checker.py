"""Assert the emulated blink app blinks PD8 — and that the composed device model
worked. Locates each plugin's model by its registered name via result.by_name(),
showing how a checker consumes multiple composed plugins.
"""


def check(result):
    gpio = result.by_name("stm32g0.gpio")
    rcc = result.by_name("blink.rcc_probe")
    assert gpio is not None, "stm32g0.gpio plugin not in the device model"
    assert rcc is not None, "blink.rcc_probe plugin not in the device model"

    # The app-local RCC plugin should have seen the port clock enabled first.
    assert rcc.gpiod_clock_enabled, "firmware never enabled the GPIOD clock"

    t = gpio.transitions
    print("  LED transitions: %s   gpiod_clock_enabled: %s" % (t, rcc.gpiod_clock_enabled))
    assert len(t) >= 4, "LED toggled only %d times; expected a blink" % len(t)
    assert t[0] == 1, "first LED transition should be ON, got %r" % t[0]
    for i in range(1, len(t)):
        assert t[i] != t[i - 1], "LED did not alternate at transition %d: %s" % (i, t)
    assert not result.hit_budget, "app hit the cycle budget before blinking enough"
