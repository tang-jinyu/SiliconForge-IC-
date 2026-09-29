import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from digital_ic_agent.api import build_app
from digital_ic_agent.auth import AuthManager
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService


class Phase1GuiTest(unittest.TestCase):
    def test_gui_endpoint_runs_suite_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            service = AgentTaskService(
                repo_root=repo_root,
                queue=FileTaskQueue(repo_root / ".agent_queue"),
            )
            app = build_app(service=service, auth_manager=AuthManager(access_password=None))
            fake_report = {"case_count": 3, "passed_cases": 3, "average_score": 100.0}

            with patch("digital_ic_agent.api.run_benchmark_suite", return_value=fake_report):
                with TestClient(app) as client:
                    started = client.post("/api/demo/phase1")
                    self.assertEqual(started.status_code, 200)
                    self.assertIn(started.json()["status"], {"running", "succeeded"})

                    deadline = time.monotonic() + 2
                    status = client.get("/api/demo/phase1").json()
                    while status["status"] == "running" and time.monotonic() < deadline:
                        time.sleep(0.01)
                        status = client.get("/api/demo/phase1").json()

                    self.assertEqual(status["status"], "succeeded")
                    self.assertEqual(status["passed_cases"], 3)
                    self.assertEqual(status["average_score"], 100.0)

    def test_competition_benchmark_reports_first_pass_and_repair_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            service = AgentTaskService(
                repo_root=repo_root,
                queue=FileTaskQueue(repo_root / ".agent_queue"),
            )
            app = build_app(service=service, auth_manager=AuthManager(access_password=None))
            fake_report = {
                "case_count": 3,
                "passed_cases": 2,
                "average_score": 82.0,
                "results": [
                    {"passed": True, "repair_attempts": 0},
                    {"passed": True, "repair_attempts": 1},
                    {"passed": False, "repair_attempts": 3},
                ],
            }

            with patch("digital_ic_agent.api.run_benchmark_suite", return_value=fake_report):
                with TestClient(app) as client:
                    started = client.post("/api/benchmark/competition")
                    self.assertEqual(started.status_code, 200)

                    deadline = time.monotonic() + 2
                    status = client.get("/api/benchmark/competition").json()
                    while status["status"] == "running" and time.monotonic() < deadline:
                        time.sleep(0.01)
                        status = client.get("/api/benchmark/competition").json()

                    self.assertEqual(status["status"], "completed")
                    self.assertEqual(status["pass_at_1_cases"], 1)
                    self.assertEqual(status["pass_after_repair_cases"], 1)

    def test_runtime_endpoint_is_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            service = AgentTaskService(
                repo_root=repo_root,
                queue=FileTaskQueue(repo_root / ".agent_queue"),
            )
            app = build_app(service=service, auth_manager=AuthManager(access_password=None))
            with TestClient(app) as client:
                response = client.get("/api/runtime")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("platform", payload)
            self.assertIn("gpu", payload)
            self.assertNotIn("api_key", str(payload).lower())


if __name__ == "__main__":
    unittest.main()
