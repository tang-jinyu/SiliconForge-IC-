# Carry Borrow ALU8 benchmark case

Generate a synthesizable Verilog-2001 module that matches the sibling task.interface.v exactly.

Functional requirements:
1. When sub = 0, compute {cout, result} = a + b + cin and force borrow = 0.
2. When sub = 1, compute result = a - b - cin using 9-bit internal arithmetic, assert borrow when a < (b + cin), and force cout = 0.
3. zero shall be high exactly when result == 8'h00.
4. Keep arithmetic width, carry, and borrow semantics explicit; do not rely on implicit signed promotion.
5. The testbench must be deterministic and self-checking, covering at least these edges: 8'hff + 1, 8'h00 - 1, and a subtraction with cin = 1.
