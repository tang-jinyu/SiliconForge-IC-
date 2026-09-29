from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from digital_ic_agent.eda import _platform_binary_names, _resolve_tool_path
from digital_ic_agent.runtime_info import _safe_endpoint, build_runtime_report


class PortabilityTest(unittest.TestCase):
    def test_platform_binary_names_are_native(self) -> None:
        names = _platform_binary_names("iverilog.exe")
        if os.name == "nt":
            self.assertIn("iverilog.exe", names)
            self.assertIn("iverilog", names)
        else:
            self.assertEqual(names, ("iverilog",))

    def test_explicit_tool_path_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = Path(temp_dir) / "custom-yosys"
            tool.write_text("", encoding="utf-8")
            with patch.dict(os.environ, {"DIGITAL_IC_AGENT_YOSYS_BIN": str(tool)}):
                self.assertEqual(
                    _resolve_tool_path(Path(temp_dir), "DIGITAL_IC_AGENT_YOSYS_BIN", "yosys"),
                    tool,
                )

    def test_runtime_report_masks_endpoint_credentials_and_query(self) -> None:
        endpoint = _safe_endpoint("https://user:secret@example.com:8443/v1?token=secret")
        self.assertEqual(endpoint, "https://example.com:8443/v1")

    def test_runtime_report_has_portability_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = build_runtime_report(Path(temp_dir))
        self.assertEqual(set(report), {"platform", "model", "gpu", "eda", "portability"})
        self.assertIn("server_ready", report["portability"])


if __name__ == "__main__":
    unittest.main()
