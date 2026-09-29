# Sync FIFO16x8 benchmark case

Generate a synthesizable Verilog-2001 synchronous FIFO that matches the sibling task.interface.v exactly.

Functional requirements:
1. Depth is 16 entries and width is 8 bits.
2. On reset, the FIFO is empty, full is low, count is 0, and dout may reset to 0.
3. A write succeeds only when wr_en is high and full is low.
4. A read succeeds only when rd_en is high and empty is low; on a successful read, dout updates to the value being popped.
5. If both read and write succeed in the same cycle, preserve FIFO ordering and keep count unchanged.
6. full and empty must track the post-cycle FIFO occupancy.
7. The testbench must be deterministic and self-checking, verifying push/pop ordering, empty/full transitions, and a simultaneous read/write case.
