# Interface Contract Counter benchmark case

Generate a synthesizable Verilog-2001 module that matches the sibling task.interface.v exactly.

Functional requirements:
1. On active-low reset, clear count and wrap_pulse.
2. When enable is high, increment count on each rising clock edge.
3. When count equals limit and enable is high, wrap count back to 0 on the next clock and assert wrap_pulse for exactly one cycle.
4. When enable is low, hold count and deassert wrap_pulse.
5. Keep the design self-contained and FPGA-friendly.
6. Generate a deterministic self-checking testbench that verifies reset, hold behavior, wrap behavior, and exact interface preservation.
