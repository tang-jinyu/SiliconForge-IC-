from __future__ import annotations

import unittest

from digital_ic_agent.code_utils import sanitize_verilog_rtl


class RtlSanitizerTests(unittest.TestCase):
    def test_explicit_wire_is_added_for_ansi_ports_under_default_nettype_none(self) -> None:
        source = """`default_nettype none
module mult66x66(
    input [65:0] a,
    input wire [65:0] b,
    output signed [131:0] p
);
assign p = a * b;
endmodule
`default_nettype wire
"""

        sanitized = sanitize_verilog_rtl(source)

        self.assertIn("input wire [65:0] a", sanitized)
        self.assertIn("input wire [65:0] b", sanitized)
        self.assertIn("output wire signed [131:0] p", sanitized)
        self.assertEqual(sanitize_verilog_rtl(sanitized), sanitized)


if __name__ == "__main__":
    unittest.main()
