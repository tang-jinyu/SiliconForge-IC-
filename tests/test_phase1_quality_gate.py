import tempfile
import unittest
from pathlib import Path

from digital_ic_agent.benchmark_runner import load_benchmark_case
from digital_ic_agent.skill_governance import build_governance_artifacts
from digital_ic_agent.task_service import AgentTaskService


class TestPhase1QualityGate(unittest.TestCase):
    def test_eda_failure_is_not_a_success(self) -> None:
        message = AgentTaskService._quality_gate_error(
            {
                "eda_result": {
                    "overall_pass": False,
                    "simulation_passed": False,
                    "synthesis_passed": True,
                }
            }
        )
        self.assertIsNotNone(message)
        self.assertIn("simulation", message)

    def test_passing_eda_clears_quality_gate(self) -> None:
        message = AgentTaskService._quality_gate_error(
            {
                "eda_result": {
                    "overall_pass": True,
                    "simulation_passed": True,
                    "synthesis_passed": True,
                }
            }
        )
        self.assertIsNone(message)

    def test_governance_artifacts_have_digest_and_pass_scan(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        artifacts = build_governance_artifacts(repo_root=repo_root, task_kind="eda_triage")
        self.assertEqual(artifacts["security_report"]["verdict"], "pass")
        self.assertEqual(len(artifacts["skill_card"]["integrity"]["package_digest"]), 64)

    def test_benchmark_metadata_paths_are_case_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case"
            case_dir.mkdir()
            (case_dir / "task.md").write_text("demo", encoding="utf-8")
            (case_dir / "benchmark_case.json").write_text(
                '{"task_kind":"eda_triage","metadata":{"rtl_path":"rtl.v","testbench_path":"tb.v"}}',
                encoding="utf-8",
            )
            case = load_benchmark_case(case_dir)
            self.assertEqual(Path(case.metadata["rtl_path"]), (case_dir / "rtl.v").resolve())
            self.assertEqual(Path(case.metadata["testbench_path"]), (case_dir / "tb.v").resolve())


if __name__ == "__main__":
    unittest.main()

