# Add8 FPGA benchmark case

Generate a synthesizable 8-bit adder module named add8.

Requirements:
1. Inputs: a[7:0], b[7:0], cin.
2. Outputs: sum[7:0], cout.
3. The RTL must be pure Verilog-2001, FPGA-friendly, and synthesizable.
4. Also generate a minimal deterministic self-checking testbench.
5. Keep the design local and self-contained.