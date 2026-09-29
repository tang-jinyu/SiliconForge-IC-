module contract_counter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    input  wire [7:0] limit,
    output reg  [7:0] count,
    output reg        wrap_pulse
);

endmodule
