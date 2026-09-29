# Overlapping sequence detector

Create synthesizable Verilog-2001 module `seq1011` with inputs `clk`, active-low synchronous reset `rst_n`, serial input `din`, and output reg `hit`. On each rising edge, after reset is released, assert `hit` for exactly one cycle whenever the most recent bits form 1011. Overlapping matches are required (e.g. 1011011 produces two pulses). Reset is sampled only on `posedge clk` and clears state and hit.
