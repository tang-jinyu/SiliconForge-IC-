# FSM Handshake Controller benchmark case

Generate a synthesizable Verilog-2001 controller that matches the sibling task.interface.v exactly.

Functional requirements:
1. cmd_ready shall be high only when the module is idle and not holding a response.
2. When cmd_valid and cmd_ready handshake, latch cmd_data, raise busy, and start a fixed three-cycle processing latency.
3. After the three-cycle latency, drive resp_data = latched cmd_data + 8'h21 and assert resp_valid.
4. While resp_valid is high and resp_ready is low, hold resp_valid, resp_data, and busy stable.
5. After resp_valid and resp_ready handshake, clear resp_valid and busy, then return to the idle state with cmd_ready high.
6. The testbench must be self-checking and explicitly verify command acceptance, latency, response hold behavior, and release after resp_ready.
