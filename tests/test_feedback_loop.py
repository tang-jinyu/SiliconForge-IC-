import json
import tempfile
import unittest
from pathlib import Path

from digital_ic_agent.feedback_loop import FeedbackLoop
from digital_ic_agent.task_models import AgentTaskRecord, AgentTaskRequest


class TestFeedbackLoop(unittest.TestCase):
    def test_capture_classifies_precheck_failure_and_updates_memory_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            output_dir = repo_root / "runs" / "case1"
            request = AgentTaskRequest(
                title="case1",
                requirement_text="Generate a FIFO module with ready/valid handshake and explicit byte order requirements.",
                output_dir=output_dir,
                task_kind="rtl_module_generation",
            )
            record = AgentTaskRecord.create(request).mark_running()
            loop = FeedbackLoop(repo_root)

            state = {
                "eda_result": {
                    "top_module": "demo",
                    "overall_pass": False,
                    "precheck_issues": [
                        "Interface contract mismatch: expected top module 'demo', got 'demo_v2'.",
                        "RTL is not self-contained. Undefined instantiated modules: fifo_sync.",
                    ],
                    "simulation_log": "[precheck]\nInterface contract mismatch",
                    "yosys_log": "[precheck]\nUndefined instantiated modules",
                },
                "repair_attempts": 1,
            }

            payload = loop.capture(record=record, state=state)

            self.assertIn("feedback_report", payload)
            self.assertIn("feedback_memory_snapshot", payload)
            self.assertIn("interface_contract_mismatch", payload["feedback_report"]["error_tags"])
            self.assertIn("undefined_helper_module", payload["feedback_report"]["error_tags"])
            self.assertIn("interface_contract_and_handshake", payload["feedback_report"]["skill_categories"])
            self.assertIn("handshake_contract_surface", payload["feedback_report"]["fingerprint_keys"])
            self.assertIn("ram_fifo_inference", payload["feedback_report"]["fingerprint_keys"])

            memory_json_path = repo_root / "project_prompt" / "output" / "fpga_feedback_memory.json"
            memory_markdown_path = repo_root / "project_prompt" / "output" / "fpga_feedback_memory.md"
            self.assertTrue(memory_json_path.exists())
            self.assertTrue(memory_markdown_path.exists())

            memory_payload = json.loads(memory_json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(memory_payload["entries"]), 1)
            self.assertEqual(memory_payload["tag_counts"]["interface_contract_mismatch"], 1)
            self.assertEqual(memory_payload["fingerprint_counts"]["handshake_contract_surface"], 1)
            self.assertIn("Top semantic fingerprints:", memory_markdown_path.read_text(encoding="utf-8"))

    def test_capture_uses_runtime_exception_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            output_dir = repo_root / "runs" / "case2"
            request = AgentTaskRequest(
                title="case2",
                requirement_text="Generate a module.",
                output_dir=output_dir,
                task_kind="rtl_module_generation",
            )
            record = AgentTaskRecord.create(request).mark_failed(error="boom", model="demo-model")
            loop = FeedbackLoop(repo_root)

            payload = loop.capture(record=record, state={}, error="LLM request timed out")

            self.assertIn("runtime_exception", payload["feedback_report"]["error_tags"])
            self.assertEqual(payload["feedback_report"]["outcome"], "runtime_failure")


if __name__ == "__main__":
    unittest.main()