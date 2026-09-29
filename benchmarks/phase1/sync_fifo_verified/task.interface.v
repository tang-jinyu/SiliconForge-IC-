module sync_fifo4x8(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       wr_en,
    input  wire       rd_en,
    input  wire [7:0] wr_data,
    output reg  [7:0] rd_data,
    output wire       full,
    output wire       empty
);
endmodule
