`timescale 1ns/1ps
module handshake_fsm_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg req = 1'b0;
    wire ack;
    wire busy;

    handshake_fsm dut (.clk(clk), .rst_n(rst_n), .req(req), .ack(ack), .busy(busy));
    always #5 clk = ~clk;

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        req = 1'b1;
        @(posedge clk);
        #1;
        if (!busy || ack) begin
            $display("FAIL: request was not captured");
            $finish;
        end
        @(negedge clk);
        req = 1'b0;
        @(posedge clk);
        #1;
        if (busy || !ack) begin
            $display("FAIL: acknowledgement was not emitted");
            $finish;
        end
        @(posedge clk);
        #1;
        if (ack) begin
            $display("FAIL: acknowledgement lasted longer than one cycle");
            $finish;
        end
        $display("PASS: handshake_fsm_verified");
        $finish;
    end
endmodule
