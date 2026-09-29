`timescale 1ns / 1ps

module hqc128_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        spi_cs_n,
    input  wire        spi_sclk,
    input  wire        spi_mosi,
    output wire        spi_miso,
    input  wire        uart_rx,
    output wire        uart_tx,
    output wire        cmd_ready,
    output wire        cmd_busy,
    output wire        result_valid,
    output wire [31:0] result_data,
    output wire        fault_detect,
    output wire [7:0]  side_chain_mon
);

endmodule
