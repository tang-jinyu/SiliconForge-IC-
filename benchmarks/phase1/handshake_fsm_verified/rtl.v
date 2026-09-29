module handshake_fsm(
    input  wire clk,
    input  wire rst_n,
    input  wire req,
    output reg  ack,
    output reg  busy
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ack  <= 1'b0;
            busy <= 1'b0;
        end else begin
            ack <= 1'b0;
            if (!busy && req) begin
                busy <= 1'b1;
            end else if (busy) begin
                busy <= 1'b0;
                ack  <= 1'b1;
            end
        end
    end
endmodule
