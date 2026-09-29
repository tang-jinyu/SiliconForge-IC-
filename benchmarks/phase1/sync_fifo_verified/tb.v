`timescale 1ns/1ps
module sync_fifo4x8_tb;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg wr_en = 1'b0;
    reg rd_en = 1'b0;
    reg [7:0] wr_data = 8'd0;
    wire [7:0] rd_data;
    wire full;
    wire empty;

    sync_fifo4x8 dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en),
        .wr_data(wr_data), .rd_data(rd_data), .full(full), .empty(empty)
    );
    always #5 clk = ~clk;

    task push;
        input [7:0] value;
        begin
            @(negedge clk);
            wr_data = value;
            wr_en = 1'b1;
            @(negedge clk);
            wr_en = 1'b0;
        end
    endtask

    task pop_and_check;
        input [7:0] expected;
        begin
            @(negedge clk);
            rd_en = 1'b1;
            @(negedge clk);
            rd_en = 1'b0;
            #1;
            if (rd_data !== expected) begin
                $display("FAIL: FIFO expected %0d, got %0d", expected, rd_data);
                $finish;
            end
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        if (!empty) begin
            $display("FAIL: FIFO not empty after reset");
            $finish;
        end
        push(8'h11);
        push(8'h22);
        push(8'h33);
        push(8'h44);
        if (!full) begin
            $display("FAIL: FIFO did not assert full");
            $finish;
        end
        pop_and_check(8'h11);
        pop_and_check(8'h22);
        pop_and_check(8'h33);
        pop_and_check(8'h44);
        if (!empty) begin
            $display("FAIL: FIFO did not return to empty");
            $finish;
        end
        $display("PASS: sync_fifo_verified");
        $finish;
    end
endmodule

