module spi_byte_counter (
    input  wire       rst_n,
    input  wire       spi_cs_n,
    input  wire       spi_sclk,
    input  wire       spi_mosi,
    output reg  [7:0] byte_count,
    output reg  [7:0] last_byte,
    output reg        frame_done
);

endmodule
