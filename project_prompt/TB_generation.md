Generate a deterministic, self-checking Verilog-2001 testbench for the frozen specification and RTL below.

Specification:
{specification}

RTL:
{rtl_code}

Requirements:
- Return exactly one complete `verilog` code block and no other code blocks.
- Instantiate the DUT with its exact declared ports; never invent shortcut or hidden ports.
- Match every width, signedness, polarity, clock, reset, and handshake rule.
- For combinational designs, do not invent clock/reset. Apply an input, wait a fixed delay, compare with a correctly sized reference expression, and count failures.
- For sequential designs, generate the declared clock/reset and check at contract-defined sampling edges with bounded timeouts.
- Cover zero, one, maximum values, alternating-bit patterns, boundary values, and at least 20 deterministic pseudo-random or enumerated cases when the space is large.
- Compute expected arithmetic values independently with correctly sized testbench registers/expressions.
- Use case inequality (`!==`) when X/Z must fail.
- Print diagnostics and exactly one final `TEST_PASS` or `TEST_FAIL` marker.
- Always terminate with `$finish`; include a watchdog for clocked/protocol designs.
- Remain compatible with Icarus Verilog; no classes, constrained randomization, DPI, UVM, or simulator-specific features.

Output only the final testbench code block.

