`timescale 1ns/1ps
module add8_tb;
    reg [7:0] a;
    reg [7:0] b;
    wire [7:0] sum;

    add8 dut (.a(a), .b(b), .sum(sum));

    task check;
        input [7:0] lhs;
        input [7:0] rhs;
        input [7:0] expected;
        begin
            a = lhs;
            b = rhs;
            #1;
            if (sum !== expected) begin
                $display("FAIL: %0d + %0d expected %0d, got %0d", lhs, rhs, expected, sum);
                $finish;
            end
        end
    endtask

    initial begin
        check(8'd0, 8'd0, 8'd0);
        check(8'd1, 8'd2, 8'd3);
        check(8'd255, 8'd1, 8'd0);
        check(8'd77, 8'd99, 8'd176);
        $display("PASS: add8_verified");
        $finish;
    end
endmodule

