# Blind RTL Benchmark v1

Each case exposes only `task.md` to the agent. `oracle_tb.v` is an independent,
hand-written testbench used by the benchmark runner after generation; it is never
included in the prompt. The suite covers combinational logic, FSM, FIFO, protocol
control, and RTL repair.
