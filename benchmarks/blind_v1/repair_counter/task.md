# Repair the supplied RTL

Repair the buggy module below while preserving exactly this interface. The intended behavior is an 8-bit saturating up/down counter: active-high synchronous reset sets q=0; when en=0 hold; when en=1 and up=1 increment unless already 8'hff; when en=1 and up=0 decrement unless already zero. Produce the complete corrected module `sat_counter8`.

```verilog
module sat_counter8(input clk,input rst,input en,input up,output reg [7:0] q);
always @(posedge clk) begin
  if (rst) q <= 8'hff;
  else if (en && up) q <= q + 1'b1;
  else if (en) q <= q - 1'b1;
end
endmodule
```
