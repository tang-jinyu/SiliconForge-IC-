from __future__ import annotations

import unittest

from digital_ic_agent.arithmetic_skill import (
    build_multiplier_rtl,
    build_multiplier_testbench,
    detect_multiplier_contract,
)
from digital_ic_agent.code_utils import sanitize_verilog_rtl


class ArithmeticSkillTests(unittest.TestCase):
    def test_detects_short_chinese_multiplier_requirement(self) -> None:
        contract = detect_multiplier_contract("设计一个66x66乘法器")
        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertEqual(contract.a_width, 66)
        self.assertEqual(contract.b_width, 66)
        self.assertEqual(contract.product_width, 132)
        self.assertEqual(contract.module_name, "mult66x66")

    def test_generated_contract_is_minimal_and_sanitizer_is_idempotent(self) -> None:
        contract = detect_multiplier_contract("设计一个66×66乘法器")
        assert contract is not None
        rtl = build_multiplier_rtl(contract)
        tb = build_multiplier_testbench(contract)
        self.assertIn("input wire [65:0] a", rtl)
        self.assertIn("output wire [131:0] p", rtl)
        self.assertNotIn("clk", rtl)
        self.assertNotIn("reset", rtl)
        self.assertEqual(sanitize_verilog_rtl(rtl), rtl)
        self.assertIn("TEST_PASS", tb)
        self.assertIn("TEST_FAIL", tb)


if __name__ == "__main__":
    unittest.main()
