module handshake_controller (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       cmd_valid,
    input  wire [7:0] cmd_data,
    output wire       cmd_ready,
    output reg        busy,
    output reg        resp_valid,
    output reg  [7:0] resp_data,
    input  wire       resp_ready
);

endmodule
