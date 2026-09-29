# 16-bit combinational ALU

Create synthesizable Verilog-2001 module `alu16` with inputs `a[15:0]`, `b[15:0]`, `op[2:0]` and outputs `y[15:0]`, `zero`, `carry`. It must be purely combinational. Operations: 000 add (`carry` is carry-out), 001 subtract (`carry` is no-borrow, i.e. a>=b), 010 AND, 011 OR, 100 XOR, 101 logical left shift of a by b[3:0], 110 logical right shift, 111 set-less-than unsigned (y=1 or 0). For non-add/sub operations carry=0. `zero` is true exactly when y is zero.
