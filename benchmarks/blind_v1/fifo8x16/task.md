# Synchronous FIFO

Create synthesizable Verilog-2001 module `sync_fifo8x16` with `clk`, active-high synchronous `rst`, `wr_en`, `rd_en`, `din[15:0]`, outputs `dout[15:0]`, `full`, `empty`, and `count[3:0]`. Depth is 8. Accepted write is wr_en&&!full; accepted read is rd_en&&!empty. A read updates dout with the oldest word. Simultaneous accepted read/write keeps count unchanged and ordering correct. Reset empties FIFO, count=0, dout=0.
