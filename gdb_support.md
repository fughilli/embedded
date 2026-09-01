Add support for GDB on both real hardware and in emulation.

For emulation, use https://github.com/bet4it/udbserver

For simulation, use the same pyocd support, but run the gdbserver stub.

Have firmware_binary() output FirmwareInfo containing the .elf, .map, etc.

Generate .debug targets:
- pyocd_debug() is a new rule that takes a FirmwareInfo provider and builds a binary that can be run to get an interactive GDB session on the target (load optional, allowing attaching to and debugging already-running targets)
- simulation_test() also outputs .debug alongside the test which has the same semantics--starts the test, and for each test case, breaks at the entry point allowing single-step
- simulation_app() also outputs .debug, breaking at the application entry point

The .debug targets themselves are composed of a python binary which starts the debug server in the background, waits for the server to start listening, and then executes gdb with the appropriate arguments to connect to the server and load the firmware binary. The gdb session should be interactive, allowing users to set breakpoints, inspect memory, and step through code. When the gdb session is terminated, the debug server should be gracefully shut down.
