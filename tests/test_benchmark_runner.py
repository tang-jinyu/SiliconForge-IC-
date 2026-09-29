import json
import tempfile
import unittest
from pathlib import Path

from digital_ic_agent.benchmark_runner import load_benchmark_case, run_benchmark_suite, score_benchmark_case
from digital_ic_agent.task_models import AgentTaskExecution, AgentTaskRecord, AgentTaskRequest


class TestBenchmarkRunner(unittest.TestCase):
    def test_load_benchmark_case_reads_expectations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case_a"
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "task.md").write_text("task text", encoding="utf-8")
            (case_dir / "benchmark_case.json").write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "title": "Case A",
                        "task_kind": "rtl_module_generation",
                        "expected": {
                            "overall_pass": True,
                            "simulation_passed": True,
                            "synthesis_passed": True,
                            "max_repair_attempts": 1,
                            "required_artifacts": ["rtl_code.v"],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            case = load_benchmark_case(case_dir)

            self.assertEqual(case.case_id, "case_a")
            self.assertTrue(case.expectation.overall_pass)
            self.assertEqual(case.expectation.required_artifacts, ("rtl_code.v",))

    def test_score_benchmark_case_returns_full_score_for_matching_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_dir = Path(temp_dir) / "case_b"
            output_dir = Path(temp_dir) / "runs" / "case_b"
            case_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "task.md").write_text("task text", encoding="utf-8")
            (case_dir / "benchmark_case.json").write_text(
                json.dumps(
                    {
                        "case_id": "case_b",
                        "title": "Case B",
                        "task_kind": "rtl_module_generation",
                        "expected": {
                            "overall_pass": True,
                            "simulation_passed": True,
                            "synthesis_passed": True,
                            "max_repair_attempts": 1,
                            "required_artifacts": ["rtl_code.v", "testbench.v"],
                            "forbidden_precheck_substrings": ["Interface contract mismatch"],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (output_dir / "rtl_code.v").write_text("module demo; endmodule\n", encoding="utf-8")
            (output_dir / "testbench.v").write_text("module demo_tb; endmodule\n", encoding="utf-8")

            case = load_benchmark_case(case_dir)
            request = AgentTaskRequest(
                title="Case B",
                requirement_text="task text",
                output_dir=output_dir,
                task_kind="rtl_module_generation",
            )
            record = AgentTaskRecord.create(request).mark_running().mark_succeeded(model="demo-model", repair_attempts=1)
            state = {
                "repair_attempts": 1,
                "eda_result": {
                    "overall_pass": True,
                    "simulation_passed": True,
                    "synthesis_passed": True,
                    "precheck_issues": [],
                },
                "feedback_report": {"error_tags": []},
            }

            result = score_benchmark_case(case, record=record, state=state)

            self.assertEqual(result["score"], 100)
            self.assertTrue(result["passed"])

    def test_run_benchmark_suite_writes_per_case_score_and_injects_metadata(self):
        class DummyService:
            def __init__(self) -> None:
                self.requests: list[AgentTaskRequest] = []

            def run_sync(self, request: AgentTaskRequest) -> AgentTaskExecution:
                self.requests.append(request)
                request.output_dir.mkdir(parents=True, exist_ok=True)
                (request.output_dir / "rtl_code.v").write_text("module demo; endmodule\n", encoding="utf-8")
                record = AgentTaskRecord.create(request).mark_succeeded(model="demo-model", repair_attempts=0)
                state = {
                    "repair_attempts": 0,
                    "eda_result": {
                        "overall_pass": True,
                        "simulation_passed": True,
                        "synthesis_passed": True,
                        "precheck_issues": [],
                    },
                    "feedback_report": {
                        "error_tags": ["interface_contract_mismatch"],
                        "fingerprint_keys": ["handshake_contract_surface"],
                    },
                }
                return AgentTaskExecution(record=record, workflow_state=state, manifest={})

        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir = Path(temp_dir) / "suite"
            case_dir = suite_dir / "case_c"
            output_dir = Path(temp_dir) / "runs"
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "task.md").write_text("task text", encoding="utf-8")
            (case_dir / "benchmark_case.json").write_text(
                json.dumps(
                    {
                        "case_id": "case_c",
                        "title": "Case C",
                        "task_kind": "rtl_module_generation",
                        "expected": {
                            "overall_pass": True,
                            "simulation_passed": True,
                            "synthesis_passed": True,
                            "required_artifacts": ["rtl_code.v"],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            service = DummyService()
            report = run_benchmark_suite(service=service, suite_dir=suite_dir, output_dir=output_dir, dry_run=True)

            self.assertEqual(report["case_count"], 1)
            self.assertEqual(service.requests[0].metadata["benchmark_case_id"], "case_c")
            self.assertEqual(service.requests[0].metadata["benchmark_suite_dir"], str(suite_dir))
            score_payload = json.loads((output_dir / "case_c" / "meta" / "benchmark_score.json").read_text(encoding="utf-8"))
            self.assertEqual(score_payload["score"], 100)
            self.assertEqual(score_payload["feedback_fingerprints"], ["handshake_contract_surface"])


if __name__ == "__main__":
    unittest.main()
