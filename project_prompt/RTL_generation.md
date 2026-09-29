Generate the final synthesizable RTL from the frozen specification below.

Specification:
{specification}

Before writing code, silently check that the module declaration exactly matches the frozen interface contract and that every specified behavior has an implementation path.

Requirements:
- Return exactly one complete `verilog` code block and no other code blocks.
- Use Verilog-2001 unless SystemVerilog is explicitly required.
- Preserve the exact module name, ports, widths, signedness, and polarities.
- Keep RTL self-contained; define every instantiated helper in the same block.
- Do not invent clock, reset, handshake, debug, SPI, UART, FIFO, transport, or status ports.
- Use `default_nettype none` and restore `default_nettype wire` at the end.
- With `default_nettype none`, explicitly write a net type on every ANSI-style net port (for example `input wire` and `output wire`); this is required by Vivado 2018.3 even when newer parsers accept an omitted net type.
- Use nonblocking assignments for sequential state and blocking assignments for combinational procedural logic.
- Avoid latches, combinational loops, delays, force/release, classes, DPI, fork/join, and nonsynthesizable constructs.
- Prefer direct operators and standard inference patterns for simple contracts; do not add an FSM to a combinational arithmetic block.
- Make widths explicit and verify arithmetic signedness and full result width.
- The code must synthesize with Yosys and simulate with Icarus Verilog.

Output only the final code block.

