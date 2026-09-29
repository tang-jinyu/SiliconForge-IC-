`timescale 1ns/1ps
module oracle_tb; reg sclk=0,rst_n=0,cs_n=1,mosi=0; wire [7:0] data; wire valid; integer i; spi_rx8 dut(.sclk(sclk),.rst_n(rst_n),.cs_n(cs_n),.mosi(mosi),.data(data),.valid(valid));
task send; input [7:0] v; begin cs_n=0; for(i=7;i>=0;i=i-1)begin mosi=v[i];#5;sclk=1;#1;if(i!=0&&valid)begin $display("FAIL: early valid");$finish;end #4;sclk=0;end #1;if(!valid||data!==v)begin $display("FAIL: spi byte");$finish;end #4;sclk=1;#1;if(valid)begin $display("FAIL: valid width");$finish;end #4;sclk=0;cs_n=1;end endtask
initial begin #2;rst_n=1;send(8'ha5);#5;send(8'h3c);$display("PASS: blind protocol");$finish;end endmodule
