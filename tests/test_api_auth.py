from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from digital_ic_agent.api import build_app
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService


class ApiAuthFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_auth_enabled_requires_login_for_dashboard_and_task_submit(self) -> None:
        client, _ = self._build_client({"DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass"})
        with client:
            session_payload = client.get("/api/auth/session")
            self.assertEqual(session_payload.status_code, 200)
            self.assertTrue(session_payload.json()["enabled"])
            self.assertFalse(session_payload.json()["authenticated"])

            dashboard = client.get("/api/dashboard")
            submit = client.post(
                "/api/tasks",
                json={
                    "title": "auth-required",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": True,
                },
            )

            self.assertEqual(dashboard.status_code, 401)
            self.assertEqual(submit.status_code, 401)

    def test_login_and_saved_llm_config_drive_runtime_without_persisting_api_key(self) -> None:
        client, service = self._build_client({"DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass"})
        captured_config: dict[str, object] = {}

        def fake_run_workflow(*args, **kwargs):
            config = kwargs["config"]
            captured_config.update(
                {
                    "api_key": config.api_key,
                    "base_url": config.base_url,
                    "model": config.model,
                    "llm_transport": config.llm_transport,
                }
            )
            return {
                "requirement_analysis": {},
                "architecture_design": {},
                "specification": "spec",
                "rtl_code": "module demo; endmodule",
                "testbench_code": "module tb; endmodule",
                "repair_attempts": 0,
            }

        with client:
            login_response = client.post(
                "/api/auth/login",
                json={"display_name": "alice", "password": "demo-pass"},
            )
            self.assertEqual(login_response.status_code, 200)
            self.assertTrue(login_response.json()["authenticated"])

            config_response = client.post(
                "/api/auth/llm-config",
                json={
                    "api_key": "user-secret-key-1234",
                    "base_url": "https://example.test/v1",
                    "model": "deepseek-chat",
                    "llm_transport": "chat",
                },
            )
            self.assertEqual(config_response.status_code, 200)
            self.assertTrue(config_response.json()["llm_config_saved"])
            self.assertEqual(config_response.json()["llm_config"]["api_key_hint"], "***1234")

            submit_response = client.post(
                "/api/tasks",
                json={
                    "title": "private-api-task",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": False,
                    "execution": "queue",
                },
            )
            self.assertEqual(submit_response.status_code, 200)
            task_id = submit_response.json()["record"]["task_id"]

            queue_record = service.get_task(task_id)
            self.assertIsNotNone(queue_record)
            queue_payload = (self.repo_root / ".agent_queue" / "tasks" / f"{task_id}.json").read_text(encoding="utf-8")
            self.assertNotIn("user-secret-key-1234", queue_payload)
            self.assertIn("auth_subject_id", queue_payload)

            with patch("digital_ic_agent.task_service.run_workflow", side_effect=fake_run_workflow):
                run_next_response = client.post("/api/tasks/run-next")

            self.assertEqual(run_next_response.status_code, 200)
            self.assertEqual(run_next_response.json()["status"], "executed")
            self.assertEqual(captured_config["api_key"], "user-secret-key-1234")
            self.assertEqual(captured_config["base_url"], "https://example.test/v1")
            self.assertEqual(captured_config["model"], "deepseek-chat")
            self.assertEqual(captured_config["llm_transport"], "chat")

    def test_public_login_does_not_fall_back_to_server_api_key_by_default(self) -> None:
        client, _ = self._build_client(
            {
                "DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass",
                "DIGITAL_IC_AGENT_API_KEY": "owner-paid-key",
                "DIGITAL_IC_AGENT_ALLOW_SHARED_LLM": "false",
            }
        )
        with client:
            self._login(client, "guest")
            response = client.post(
                "/api/tasks",
                json={
                    "title": "guest-task",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": False,
                    "execution": "queue",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("personal API configuration", response.json()["detail"])

    def test_explicit_shared_llm_mode_supports_local_h100_service(self) -> None:
        client, _ = self._build_client(
            {
                "DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass",
                "DIGITAL_IC_AGENT_API_KEY": "local-h100",
                "DIGITAL_IC_AGENT_ALLOW_SHARED_LLM": "true",
            }
        )
        with client:
            self._login(client, "guest")
            response = client.post(
                "/api/tasks",
                json={
                    "title": "local-h100-task",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": False,
                    "execution": "queue",
                },
            )

        self.assertEqual(response.status_code, 200)

    def test_dashboard_and_execution_are_scoped_per_logged_in_user(self) -> None:
        client_alice, _ = self._build_client({"DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass"})
        client_bob, service = self._build_client({"DIGITAL_IC_AGENT_ACCESS_PASSWORD": "demo-pass"})

        def fake_run_workflow(*args, **kwargs):
            return {
                "requirement_analysis": {},
                "architecture_design": {},
                "specification": "spec",
                "rtl_code": "module demo; endmodule",
                "testbench_code": "module tb; endmodule",
                "repair_attempts": 0,
            }

        with client_alice, client_bob:
            self._login(client_alice, "alice")
            self._login(client_bob, "bob")

            alice_submit = client_alice.post(
                "/api/tasks",
                json={
                    "title": "alice-task",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": True,
                    "execution": "queue",
                },
            )
            bob_submit = client_bob.post(
                "/api/tasks",
                json={
                    "title": "bob-task",
                    "task_kind": "digital_ic_workflow",
                    "requirement_text": "Build a tiny counter.",
                    "dry_run": True,
                    "execution": "queue",
                },
            )
            self.assertEqual(alice_submit.status_code, 200)
            self.assertEqual(bob_submit.status_code, 200)

            alice_dashboard = client_alice.get("/api/dashboard")
            bob_dashboard = client_bob.get("/api/dashboard")
            self.assertEqual([item["status"]["title"] for item in alice_dashboard.json()["tasks"]], ["alice-task"])
            self.assertEqual([item["status"]["title"] for item in bob_dashboard.json()["tasks"]], ["bob-task"])

            with patch("digital_ic_agent.task_service.run_workflow", side_effect=fake_run_workflow):
                bob_run = client_bob.post("/api/tasks/run-next")

            self.assertEqual(bob_run.status_code, 200)
            self.assertEqual(bob_run.json()["record"]["request"]["title"], "bob-task")

            alice_record = service.get_task(alice_submit.json()["record"]["task_id"])
            bob_record = service.get_task(bob_submit.json()["record"]["task_id"])
            self.assertIsNotNone(alice_record)
            self.assertIsNotNone(bob_record)
            self.assertEqual(alice_record.status, "pending")
            self.assertEqual(bob_record.status, "succeeded")

    def _build_client(self, env: dict[str, str]) -> tuple[TestClient, AgentTaskService]:
        with patch.dict(os.environ, env, clear=False):
            service = AgentTaskService(
                repo_root=self.repo_root,
                queue=FileTaskQueue(self.repo_root / ".agent_queue"),
            )
            client = TestClient(build_app(service=service))
        return client, service

    @staticmethod
    def _login(client: TestClient, display_name: str) -> None:
        response = client.post(
            "/api/auth/login",
            json={"display_name": display_name, "password": "demo-pass"},
        )
        assert response.status_code == 200


if __name__ == "__main__":
    unittest.main()
