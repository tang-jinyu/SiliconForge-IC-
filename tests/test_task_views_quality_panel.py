import json
import tempfile
import unittest
from pathlib import Path

from digital_ic_agent.task_models import AgentTaskRecord, AgentTaskRequest
from digital_ic_agent.task_views import TaskSummaryService


class TestTaskViewsQualityPanel(unittest.TestCase):
    def test_build_detail_exposes_quality_panel_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            output_dir = repo_root / "runs" / "case_quality"
            output_dir.mkdir(parents=True, exist_ok=True)
            request = AgentTaskRequest(
                title="quality-case",
                requirement_text="Generate a handshake controller.",
                output_dir=output_dir,
                task_kind="rtl_module_generation",
            )
            record = AgentTaskRecord.create(request).mark_succeeded(model="demo-model", repair_attempts=1)

            (output_dir / "benchmark_score.json").write_text(
                json.dumps(
                    {
                        "case_id": "fsm_handshake_controller",
                        "title": "FSM handshake controller",
                        "score": 83,
                        "passed": False,
                        "task_status": "failed",
                        "repair_attempts": 1,
                        "feedback_tags": ["simulation_self_check_failure"],
                        "feedback_fingerprints": ["state_hold_visibility"],
                        "checks": [
                            {
                                "name": "simulation_passed",
                                "weight": 2,
                                "passed": False,
                                "detail": "expected simulation_passed=True, actual=False",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (output_dir / "feedback_report.json").write_text(
                json.dumps(
                    {
                        "outcome": "simulation_failure",
                        "error_tags": ["simulation_self_check_failure"],
                        "skill_categories": ["latency_and_observability"],
                        "fingerprint_keys": ["state_hold_visibility"],
                        "recommended_guardrails": ["Hold contract-visible status and result signals long enough for external sampling instead of emitting transient pulses."],
                        "semantic_fingerprints": [
                            {
                                "key": "state_hold_visibility",
                                "title": "State Hold and Observability",
                                "skill_key": "latency_and_observability",
                                "evidence": "Context: resp_valid; Failure: FAIL: response dropped early",
                                "summary": "Hold contract-visible status and result signals long enough for external sampling instead of emitting transient pulses.",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            memory_dir = repo_root / "project_prompt" / "output"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "fpga_feedback_memory.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-05-29T00:00:00+00:00",
                        "entries": [
                            {
                                "recommended_guardrails": [
                                    "Define and preserve cycle-level handshake meaning before adjusting local control logic.",
                                    "Hold contract-visible status and result signals long enough for external sampling instead of emitting transient pulses.",
                                ]
                            }
                        ],
                        "tag_counts": {"simulation_self_check_failure": 2},
                        "skill_counts": {"latency_and_observability": 2},
                        "fingerprint_counts": {"state_hold_visibility": 2},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            service = TaskSummaryService(repo_root=repo_root)
            detail = service.build_detail(record)

            self.assertIsNotNone(detail.quality_panel)
            self.assertTrue(detail.quality_panel.benchmark.available)
            self.assertEqual(detail.quality_panel.benchmark.feedback_fingerprints, ["state_hold_visibility"])
            self.assertTrue(detail.quality_panel.feedback_report.available)
            self.assertEqual(detail.quality_panel.feedback_report.fingerprint_keys, ["state_hold_visibility"])
            self.assertTrue(detail.quality_panel.feedback_memory.available)
            self.assertEqual(detail.quality_panel.feedback_memory.top_fingerprints[0].key, "state_hold_visibility")
            self.assertIn(
                "Hold contract-visible status and result signals long enough for external sampling instead of emitting transient pulses.",
                detail.quality_panel.feedback_memory.recent_guardrails,
            )
            self.assertTrue(any(item.file_name == "benchmark_score.json" for item in detail.artifact_previews))


if __name__ == "__main__":
    unittest.main()
