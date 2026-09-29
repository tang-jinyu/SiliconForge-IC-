# SPI public stimulus benchmark case

Generate a synthesizable Verilog-2001 module that matches the sibling task.interface.v exactly.

Functional requirements:
1. Treat spi_sclk as the shifting clock and sample spi_mosi on each rising edge while spi_cs_n is low.
2. Shift MSB-first and collect bytes in groups of 8 bits.
3. After each full byte, increment byte_count, update last_byte, and assert frame_done for exactly one spi_sclk cycle.
4. When spi_cs_n is high, clear the partial bit counter and frame_done, but preserve byte_count and last_byte.
5. Keep the implementation self-contained and synthesizable.
6. The testbench must be deterministic and self-checking, and it must drive only the public pins spi_cs_n, spi_sclk, and spi_mosi rather than any hidden helper wires.
