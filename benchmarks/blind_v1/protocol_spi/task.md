# SPI mode-0 byte receiver

Create synthesizable Verilog-2001 module `spi_rx8` with inputs `sclk`, active-low asynchronous reset `rst_n`, active-low chip select `cs_n`, and `mosi`; outputs reg `data[7:0]` and `valid`. SPI mode 0: sample MOSI on each rising edge of sclk while cs_n=0, MSB first. After exactly eight sampled bits, update data and pulse valid for one sclk cycle. Deasserting cs_n aborts and clears a partial word; valid must be low while deselected.
