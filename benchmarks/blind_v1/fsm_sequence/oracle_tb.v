`timescale 1ns/1ps
module oracle_tb; reg clk=0,rst_n=0,din=0; wire hit; integer n=0; reg [3:0] hist=0; reg valid=0; seq1011 dut(.clk(clk),.rst_n(rst_n),.din(din),.hit(hit)); always #5 clk=~clk;
task bitin; input v; reg expected; begin din=v; @(posedge clk); #1; hist={hist[2:0],v}; n=n+1; expected=(n>=4 && hist==4'b1011); if(hit!==expected) begin $display("FAIL: FSM n=%0d hist=%b hit=%b",n,hist,hit);$finish;end end endtask
initial begin repeat(2) @(posedge clk); #1; rst_n=1; bitin(1);bitin(0);bitin(1);bitin(1);bitin(0);bitin(1);bitin(1); $display("PASS: blind fsm");$finish;end endmodule
