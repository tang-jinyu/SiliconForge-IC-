import unittest

from digital_ic_agent.prechecks import validate_rtl_prechecks


class PrecheckQualityRulesTest(unittest.TestCase):
    def test_rejects_blocking_assignments_in_sequential_logic(self):
        rtl_code = """
        module bad_seq (
            input wire clk,
            input wire rst_n,
            input wire d,
            output reg q
        );
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    q = 1'b0;
                end else begin
                    q = d;
                end
            end
        endmodule
        """

        issues, _interface_failed, _missing_modules = validate_rtl_prechecks(rtl_code, "")

        self.assertTrue(any("blocking assignments in edge-sensitive always blocks" in item for item in issues))

    def test_rejects_nonblocking_assignments_in_combinational_logic(self):
        rtl_code = """
        module bad_comb (
            input wire a,
            input wire b,
            output reg y
        );
            always @(*) begin
                y <= a & b;
            end
        endmodule
        """

        issues, _interface_failed, _missing_modules = validate_rtl_prechecks(rtl_code, "")

        self.assertTrue(any("nonblocking assignments in combinational always blocks" in item for item in issues))

    def test_rejects_multiple_procedural_drivers(self):
        rtl_code = """
        module bad_multi (
            input wire clk,
            input wire rst_n,
            input wire a,
            input wire b,
            output reg y
        );
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    y <= 1'b0;
                end else begin
                    y <= a;
                end
            end

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    y <= 1'b0;
                end else begin
                    y <= b;
                end
            end
        endmodule
        """

        issues, _interface_failed, _missing_modules = validate_rtl_prechecks(rtl_code, "")

        self.assertTrue(any("same procedural target from multiple always blocks" in item for item in issues))

    def test_rejects_delay_controls_in_rtl(self):
        rtl_code = """
        module bad_delay (
            input wire clk,
            input wire d,
            output reg q
        );
            always @(posedge clk) begin
                q <= #1 d;
            end
        endmodule
        """

        issues, _interface_failed, _missing_modules = validate_rtl_prechecks(rtl_code, "")

        self.assertTrue(any("delay controls (#)" in item for item in issues))

    def test_allows_clean_single_process_rtl(self):
        rtl_code = """
        module good_seq (
            input wire clk,
            input wire rst_n,
            input wire d,
            output reg q
        );
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    q <= 1'b0;
                end else begin
                    q <= d;
                end
            end
        endmodule
        """

        issues, _interface_failed, _missing_modules = validate_rtl_prechecks(rtl_code, "")

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()