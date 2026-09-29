from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from digital_ic_agent.api import build_app
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService
from digital_ic_agent.template_library import TemplateLibrary


class TemplateLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_builtin_library_exposes_five_parameterized_categories(self) -> None:
        templates = TemplateLibrary(self.root).list_templates()

        self.assertEqual(len(templates), 5)
        self.assertEqual(
            {item["category"] for item in templates},
            {"组合运算", "有限状态与序列控制", "FIFO", "协议控制器", "修复任务"},
        )
        self.assertTrue(all(item["parameterized"] for item in templates))

    def test_builtin_template_replaces_parameters_without_model_call(self) -> None:
        rendered = TemplateLibrary(self.root).render("builtin_comb_alu", {"WIDTH": 32})

        self.assertIn("parameter WIDTH = 32", rendered.rtl_code)
        self.assertNotIn("{{WIDTH}}", rendered.rtl_code)
        self.assertEqual(rendered.parameters, {"WIDTH": 32})

    def test_personal_template_requires_verified_delivery(self) -> None:
        output = self._make_delivery(overall_pass=False)

        with self.assertRaisesRegex(ValueError, "质量门"):
            TemplateLibrary(self.root).add_from_task(
                task_id="task-1", title="示例", output_dir=output, requirement_text="示例需求"
            )

    def test_personal_template_discovers_numeric_parameters(self) -> None:
        output = self._make_delivery(overall_pass=True)
        library = TemplateLibrary(self.root)
        saved = library.add_from_task(
            task_id="task-1", title="示例", output_dir=output, requirement_text="示例需求"
        )
        rendered = library.render(saved["template_id"], {"WIDTH": 24})

        self.assertTrue(saved["parameterized"])
        self.assertIn("parameter WIDTH = 24", rendered.rtl_code)
        self.assertIn("localparam WIDTH = 24", rendered.testbench_code)

    def test_template_api_lists_library_and_rejects_invalid_fifo_depth(self) -> None:
        service = AgentTaskService(
            repo_root=self.root,
            queue=FileTaskQueue(self.root / ".agent_queue"),
        )
        with TestClient(build_app(service=service)) as client:
            listed = client.get("/api/templates")
            invalid = client.post(
                "/api/templates/builtin_sync_fifo/instantiate",
                json={"parameters": {"DATA_WIDTH": 8, "DEPTH": 7}},
            )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 5)
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("2 的幂", invalid.json()["detail"])

    def _make_delivery(self, *, overall_pass: bool) -> Path:
        output = self.root / "run"
        for name in ("rtl", "tb", "doc"):
            (output / name).mkdir(parents=True, exist_ok=True)
        (output / "rtl" / "rtl_code.v").write_text(
            "module demo #(parameter WIDTH=8)(input [WIDTH-1:0] a, output [WIDTH-1:0] y); assign y=a; endmodule",
            encoding="utf-8",
        )
        (output / "tb" / "testbench.v").write_text(
            "module tb; localparam WIDTH=8; endmodule", encoding="utf-8"
        )
        (output / "doc" / "specification.md").write_text("# 规格", encoding="utf-8")
        (output / "doc" / "eda_result.json").write_text(
            json.dumps({"overall_pass": overall_pass}), encoding="utf-8"
        )
        return output


if __name__ == "__main__":
    unittest.main()
