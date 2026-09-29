Apply the following FPGA-oriented constraints strictly when generating or revising RTL:

[General FPGA Constraints]
- The design target is FPGA, so prefer coding styles that infer FPGA primitives/resources cleanly.
- Keep the design synchronous and single-clock unless otherwise specified.
- Do not generate gated clocks.
- Use clock-enable instead of creating derived clocks whenever possible.
- Keep reset usage consistent across the whole design.

[Reset Constraints]
- Explicitly choose either synchronous reset or asynchronous reset and use it consistently.
- Do not mix reset styles casually across modules.
- Reset behavior must be deterministic.
- Registers that must have a defined startup value should be explicitly reset if needed.

[RTL Synthesizability Constraints]
- Use synthesizable Verilog-2001 only.
- Do not use:
  - #delay
  - initial blocks for core functional logic unless explicitly justified for FPGA power-up behavior
  - force/release
  - fork/join
  - wait with non-synthesizable semantics
  - real/integer arithmetic beyond synthesizable intent
  - event variables
  - procedural assignments to wires
- Avoid multiple drivers on the same signal.
- Avoid combinational loops.
- Avoid latch inference by fully assigning combinational signals.

[Sequential Logic Constraints]
- Use nonblocking assignments in clocked always blocks.
- Use one clear clock edge per sequential always block.
- If clock enable is needed, code it explicitly inside the sequential block.
- Do not model behavior that depends on simulation-only timing.

[Combinational Logic Constraints]
- Use blocking assignments in combinational always blocks.
- Provide default assignments for combinational outputs and next-state signals.
- Ensure combinational logic is complete and does not infer latches.

[FSM Constraints]
- If using an FSM, use a clear state transition structure.
- Make reset state explicit.
- Define outputs clearly as Moore or Mealy style.
- Avoid overly clever state encodings unless necessary.
- Keep transitions deterministic.

[Counter / Arithmetic Constraints]
- Make bit widths explicit.
- Avoid accidental overflow/underflow ambiguity.
- If saturation or wraparound is required, state it clearly and implement it explicitly.
- Ensure comparison thresholds match signal widths.

[Memory / Array Constraints]
- If RAM/ROM/FIFO behavior is required, use inference-friendly coding style.
- Be explicit about read/write behavior.
- Avoid unsupported multi-port behavior unless intentionally designed.
- Prefer simple synchronous memory style for FPGA friendliness.

[Interface Constraints]
- Define all ports with explicit widths.
- Avoid inout unless absolutely necessary.
- Avoid internal tri-state buses.
- Keep handshake protocols explicit if used.

[Tool Compatibility Constraints]
- The code should pass basic parsing and synthesis sanity checks in Yosys.
- The code should compile in Icarus Verilog or Verilator for simulation.
- Prefer portable coding style over vendor-specific primitives unless explicitly requested.

[Output Quality Constraints]
- Keep the design readable.
- Use meaningful signal names.
- Add short comments for critical logic.
- Prefer correctness and robustness over compact clever code.

When there is a tradeoff, prioritize:
1. Synthesizability
2. Functional correctness
3. FPGA-friendly mapping
4. Readability
5. Generality