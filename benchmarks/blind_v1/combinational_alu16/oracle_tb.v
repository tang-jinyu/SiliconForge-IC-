`timescale 1ns/1ps
module oracle_tb; reg [15:0] a,b; reg [2:0] op; wire [15:0] y; wire zero,carry; integer i; reg [16:0] exp;
alu16 dut(.a(a),.b(b),.op(op),.y(y),.zero(zero),.carry(carry));
task check; input [15:0] aa,bb; input [2:0] oo; reg [15:0] ey; reg ec; begin a=aa;b=bb;op=oo; #1; ec=0; case(oo) 0:begin exp={1'b0,aa}+{1'b0,bb};ey=exp[15:0];ec=exp[16];end 1:begin ey=aa-bb;ec=(aa>=bb);end 2:ey=aa&bb;3:ey=aa|bb;4:ey=aa^bb;5:ey=aa<<bb[3:0];6:ey=aa>>bb[3:0];default:ey=(aa<bb)?16'd1:16'd0;endcase if(y!==ey||carry!==ec||zero!==(ey==0)) begin $display("FAIL: ALU");$finish;end end endtask
initial begin check(16'hffff,1,0);check(0,1,1);check(16'h55aa,16'h0f0f,2);check(16'h55aa,16'h0f0f,3);check(16'h55aa,16'h0f0f,4);check(1,4,5);check(16'h8000,15,6);check(2,3,7); $display("PASS: blind combinational");$finish;end endmodule
