from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from digital_ic_agent.api import _build_dashboard_events, build_app
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService


class _BlockingHttpClient:
    def __init__(self, *args, **kwargs) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeBackgroundResponse:
    def __init__(self, *, response_id: str, status: str, output_text: str = "") -> None:
        self.id = response_id
        self.status = status
        self.output_text = output_text
        self.error = None
        self.incomplete_details = None


class _BlockingResponsesApi:
    def __init__(self, started: threading.Event, cancelled: threading.Event) -> None:
        self._started = started
        self._cancelled = cancelled

    def create(self, **kwargs):
        self._started.set()
        return _FakeBackgroundResponse(response_id="resp-api-cancel", status="queued")

    def parse(self, **kwargs):
        self._started.set()
        return _FakeBackgroundResponse(response_id="resp-api-cancel", status="queued")

    def retrieve(self, response_id: str, **kwargs):
        if self._cancelled.is_set():
            return _FakeBackgroundResponse(response_id=response_id, status="cancelled")
        return _FakeBackgroundResponse(response_id=response_id, status="in_progress")

    def cancel(self, response_id: str, **kwargs):
        self._cancelled.set()
        return _FakeBackgroundResponse(response_id=response_id, status="cancelled")


class _FakeOpenAIClient:
    def __init__(self, responses_api) -> None:
        self.responses = responses_api
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ApiRealtimeAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.service = AgentTaskService(
            repo_root=self.repo_root,
            queue=FileTaskQueue(self.repo_root / ".agent_queue"),
        )
        self.client = TestClient(build_app(service=self.service))

    def tearDown(self) -> None:
        self.client.close()
        self.temp_dir.cleanup()

    def test_stream_tasks_once_returns_snapshot(self) -> None:
        self._submit_task(title="sse-once")

        response = self.client.get("/api/stream/tasks?once=true", headers={"accept": "text/event-stream"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-cache")
        self.assertIn("event: snapshot", response.text)
        self.assertIn('"tasks":', response.text)

    def test_upload_asset_updates_summary_and_gallery(self) -> None:
        task_id = self._submit_task(title="upload-cover")

        upload_payload = self._upload_asset(
            task_id,
            file_name="board.svg",
            fill="#ff9966",
            asset_type="board_photo",
            caption="KC705 board hero shot",
            is_cover=True,
        )
        summary = self.client.get(f"/api/tasks/{task_id}/summary")
        dashboard = self.client.get("/api/dashboard")

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)

        summary_payload = summary.json()
        dashboard_payload = dashboard.json()
        self.assertEqual(len(summary_payload["cover_assets"]), 1)
        self.assertTrue(upload_payload["asset"]["url"].startswith(f"/task-assets/{task_id}/"))
        self.assertEqual(dashboard_payload["gallery"][0]["image_url"], upload_payload["asset"]["url"])
        self.assertIsNone(dashboard_payload["gallery"][0]["fallback_scene_url"])

    def test_set_cover_switches_to_latest_asset(self) -> None:
        task_id = self._submit_task(title="switch-cover")
        first_asset = self._upload_asset(
            task_id,
            file_name="first.svg",
            fill="#ffaa66",
            asset_type="board_photo",
            caption="first cover",
            is_cover=False,
        )
        second_asset = self._upload_asset(
            task_id,
            file_name="second.svg",
            fill="#66ccff",
            asset_type="waveform_capture",
            caption="second cover",
            is_cover=False,
        )

        response = self.client.post(
            f"/api/tasks/{task_id}/assets/{second_asset['asset']['asset_id']}/cover"
        )

        self.assertEqual(response.status_code, 200)
        summary_payload = response.json()["summary"]
        cover_asset = next(asset for asset in summary_payload["cover_assets"] if asset["is_cover"])
        self.assertEqual(len(summary_payload["cover_assets"]), 2)
        self.assertNotEqual(first_asset["asset"]["asset_id"], second_asset["asset"]["asset_id"])
        self.assertEqual(cover_asset["asset_id"], second_asset["asset"]["asset_id"])
        self.assertEqual(cover_asset["asset_type"], "waveform_capture")

    def test_cancel_pending_task_marks_it_canceled(self) -> None:
        task_id = self._submit_task(title="cancel-me")

        response = self.client.post(f"/api/tasks/{task_id}/cancel")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["record"]["status"], "canceled")
        self.assertEqual(payload["summary"]["progress"]["current_stage"], "canceled")
        self.assertIn("retry", payload["summary"]["available_actions"])
        self.assertNotIn("cancel", payload["summary"]["available_actions"])

    def test_cancel_running_task_requests_cancel_and_worker_finishes_canceled(self) -> None:
        task_id = self._submit_task(title="cancel-running")
        reached_running_stage = threading.Event()
        execution_holder: dict[str, object] = {}

        def fake_run_workflow(*args, **kwargs):
            stage_checkpoint = kwargs["stage_checkpoint"]
            cancellation_check = kwargs["cancellation_check"]
            stage_checkpoint(
                "analyze_requirement:complete",
                {
                    "requirement_analysis": {
                        "task_summary": "running cancel test",
                        "inputs": [],
                        "outputs": [],
                        "constraints": [],
                        "performance_targets": [],
                        "technical_risks": [],
                        "questions_to_clarify": [],
                    }
                },
            )
            reached_running_stage.set()
            while True:
                cancellation_check("fake_workflow:wait")
                time.sleep(0.05)

        def worker() -> None:
            execution_holder["execution"] = self.service.run_next_queued()

        with patch("digital_ic_agent.task_service.run_workflow", side_effect=fake_run_workflow):
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            self.assertTrue(reached_running_stage.wait(timeout=5))

            cancel_response = self.client.post(f"/api/tasks/{task_id}/cancel")

            self.assertEqual(cancel_response.status_code, 200)
            cancel_payload = cancel_response.json()
            self.assertEqual(cancel_payload["record"]["status"], "running")
            self.assertTrue(cancel_payload["record"]["cancel_requested"])
            self.assertEqual(cancel_payload["summary"]["progress"]["current_stage"], "cancel_requested")
            self.assertEqual(cancel_payload["summary"]["progress"]["stage_label"], "取消中")
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

        final_record = self.service.get_task(task_id)
        self.assertIsNotNone(final_record)
        self.assertEqual(final_record.status, "canceled")
        self.assertEqual(final_record.cancellation_stage, "fake_workflow:wait")
        self.assertIsNotNone(execution_holder.get("execution"))
        self.assertTrue((final_record.request.output_dir / "doc" / "requirement_analysis.json").exists())

    def test_cancel_running_task_aborts_inflight_llm_request(self) -> None:
        task_id = self._submit_task(title="cancel-inflight-llm", dry_run=False)
        llm_started = threading.Event()
        provider_cancelled = threading.Event()

        def worker() -> None:
            self.service.run_next_queued()

        with patch.dict(
            os.environ,
            {
                "DIGITAL_IC_AGENT_API_KEY": "test-key",
                "DIGITAL_IC_AGENT_LLM_TRANSPORT": "responses_background",
            },
            clear=False,
        ):
            with patch(
                "digital_ic_agent.llm.OpenAI",
                lambda **kwargs: _FakeOpenAIClient(_BlockingResponsesApi(llm_started, provider_cancelled)),
            ):
                with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                    thread = threading.Thread(target=worker, daemon=True)
                    thread.start()
                    self.assertTrue(llm_started.wait(timeout=5))

                    cancel_response = self.client.post(f"/api/tasks/{task_id}/cancel")

                    self.assertEqual(cancel_response.status_code, 200)
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())

                self.assertTrue(provider_cancelled.wait(timeout=1))
        final_record = self.service.get_task(task_id)
        self.assertIsNotNone(final_record)
        self.assertEqual(final_record.status, "canceled")
        self.assertEqual(final_record.cancellation_stage, "analyze_requirement:llm")

    def test_retry_creates_fresh_pending_task(self) -> None:
        task_id = self._submit_task(title="retry-me")
        cancel_response = self.client.post(f"/api/tasks/{task_id}/cancel")
        self.assertEqual(cancel_response.status_code, 200)

        retry_response = self.client.post(f"/api/tasks/{task_id}/retry")

        self.assertEqual(retry_response.status_code, 200)
        payload = retry_response.json()
        self.assertEqual(payload["source_task_id"], task_id)
        self.assertEqual(payload["record"]["status"], "pending")
        self.assertNotEqual(payload["record"]["task_id"], task_id)
        self.assertEqual(payload["record"]["request"]["metadata"]["retry_of"], task_id)
        self.assertTrue(payload["record"]["request"]["output_dir"].endswith("_retry1"))

    def test_task_detail_and_preview_endpoints_return_artifacts_and_logs(self) -> None:
        task_id = self._submit_task(title="detail-view")
        task = self.service.get_task(task_id)
        self.assertIsNotNone(task)
        output_dir = task.request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "llm_trace.json").write_text(
            '{\n'
            '  "transport": "responses_background",\n'
            '  "transport_requested": "auto",\n'
            '  "response_id": "resp_detail_123",\n'
            '  "response_status": "cancelled",\n'
            '  "last_operation_label": "analyze_requirement:llm",\n'
            '  "provider_cancel_requested": true,\n'
            '  "provider_cancel_completed": true,\n'
            '  "capability_probe": {\n'
            '    "source": "startup_probe",\n'
            '    "supports_responses_background": true,\n'
            '    "detail": "probe ok"\n'
            '  }\n'
            '}',
            encoding="utf-8",
        )
        (output_dir / "rtl_code.v").write_text("module demo; endmodule\n", encoding="utf-8")
        (output_dir / "simulation.log").write_text("PASS\nwaveform stable\n", encoding="utf-8")
        self._upload_asset(
            task_id,
            file_name="preview.svg",
            fill="#ffd966",
            asset_type="artifact_preview",
            caption="rtl snapshot",
            is_cover=True,
        )

        detail_response = self.client.get(f"/api/tasks/{task_id}/detail")
        artifacts_response = self.client.get(f"/api/tasks/{task_id}/artifacts")
        logs_response = self.client.get(f"/api/tasks/{task_id}/logs")
        artifact_file_response = self.client.get(f"/api/tasks/{task_id}/artifacts/rtl_code.v")
        log_file_response = self.client.get(f"/api/tasks/{task_id}/logs/simulation.log")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(artifacts_response.status_code, 200)
        self.assertEqual(logs_response.status_code, 200)
        self.assertEqual(artifact_file_response.status_code, 200)
        self.assertEqual(log_file_response.status_code, 200)

        detail_payload = detail_response.json()
        artifact_previews = detail_payload["detail"]["artifact_previews"]
        log_previews = detail_payload["detail"]["log_previews"]
        self.assertEqual(len(detail_payload["detail"]["assets"]), 1)
        self.assertEqual(detail_payload["detail"]["llm_execution"]["transport"], "responses_background")
        self.assertEqual(detail_payload["detail"]["llm_execution"]["response_id"], "resp_detail_123")
        self.assertTrue(detail_payload["detail"]["llm_execution"]["provider_cancel_completed"])
        self.assertTrue(any(item["file_name"] == "llm_trace.json" for item in artifact_previews))
        self.assertTrue(any(item["file_name"] == "rtl_code.v" for item in artifact_previews))
        self.assertTrue(any(item["file_name"] == "simulation.log" for item in log_previews))
        self.assertIn("module demo", artifact_file_response.text)
        self.assertIn("waveform stable", log_file_response.text)

    def test_retry_detail_returns_diff_previews_and_waveform_assets(self) -> None:
        source_task_id = self._submit_task(title="diff-waveform")
        source_task = self.service.get_task(source_task_id)
        self.assertIsNotNone(source_task)
        source_task.request.output_dir.mkdir(parents=True, exist_ok=True)
        (source_task.request.output_dir / "rtl_code.v").write_text("module demo; endmodule\n", encoding="utf-8")
        (source_task.request.output_dir / "simulation.log").write_text("PASS\nold waveform\n", encoding="utf-8")

        cancel_response = self.client.post(f"/api/tasks/{source_task_id}/cancel")
        self.assertEqual(cancel_response.status_code, 200)
        retry_response = self.client.post(f"/api/tasks/{source_task_id}/retry")
        self.assertEqual(retry_response.status_code, 200)
        retry_task_id = retry_response.json()["record"]["task_id"]
        retry_task = self.service.get_task(retry_task_id)
        self.assertIsNotNone(retry_task)
        retry_task.request.output_dir.mkdir(parents=True, exist_ok=True)
        (retry_task.request.output_dir / "rtl_code.v").write_text(
            "module demo; wire flag; assign flag = 1'b1; endmodule\n",
            encoding="utf-8",
        )
        (retry_task.request.output_dir / "simulation.log").write_text(
            "PASS\nnew waveform\n",
            encoding="utf-8",
        )
        self._upload_asset(
            retry_task_id,
            file_name="wave.svg",
            fill="#66ccff",
            asset_type="waveform_capture",
            caption="timing waveform",
            is_cover=False,
        )

        detail_response = self.client.get(f"/api/tasks/{retry_task_id}/detail")

        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()["detail"]
        self.assertEqual(len(detail_payload["waveform_assets"]), 1)
        self.assertEqual(detail_payload["waveform_assets"][0]["asset_type"], "waveform_capture")
        diff_files = {item["file_name"] for item in detail_payload["diff_previews"]}
        self.assertIn("rtl_code.v", diff_files)
        self.assertIn("simulation.log", diff_files)
        rtl_diff = next(item for item in detail_payload["diff_previews"] if item["file_name"] == "rtl_code.v")
        self.assertIn("assign flag = 1'b1", rtl_diff["preview_text"])
        self.assertEqual(rtl_diff["source_task_id"], source_task_id)

    def test_dashboard_event_builder_emits_incremental_task_and_gallery_updates(self) -> None:
        previous = {
            "tasks": [
                {
                    "status": {"task_id": "task-a", "title": "task-a", "status": "pending"},
                    "progress": {"percent": 0},
                    "eda_summary": {"available": False},
                    "repair_history": [],
                    "cover_assets": [],
                    "available_actions": ["detail", "cancel"],
                }
            ],
            "gallery": [{"task_id": "task-a", "image_url": None}],
        }
        current = {
            "tasks": [
                {
                    "status": {"task_id": "task-a", "title": "task-a", "status": "running"},
                    "progress": {"percent": 40},
                    "eda_summary": {"available": False},
                    "repair_history": [],
                    "cover_assets": [],
                    "available_actions": ["detail"],
                },
                {
                    "status": {"task_id": "task-b", "title": "task-b", "status": "pending"},
                    "progress": {"percent": 0},
                    "eda_summary": {"available": False},
                    "repair_history": [],
                    "cover_assets": [],
                    "available_actions": ["detail", "cancel"],
                },
            ],
            "gallery": [{"task_id": "task-b", "image_url": "/task-assets/task-b/cover.svg"}],
        }

        events = _build_dashboard_events(previous, current)

        event_names = [event_name for event_name, _ in events]
        self.assertIn("task-upsert", event_names)
        self.assertIn("gallery-updated", event_names)
        self.assertNotIn("task-remove", event_names)

    def _submit_task(self, *, title: str, dry_run: bool = True) -> str:
        response = self.client.post(
            "/api/tasks",
            json={
                "title": title,
                "task_kind": "rtl_module_generation",
                "execution": "queue",
                "dry_run": dry_run,
                "requirement_text": "Generate a simple GPIO debounce module with a deterministic self-checking testbench.",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["record"]["task_id"]

    def _upload_asset(
        self,
        task_id: str,
        *,
        file_name: str,
        fill: str,
        asset_type: str,
        caption: str,
        is_cover: bool,
    ) -> dict:
        response = self.client.post(
            f"/api/tasks/{task_id}/assets",
            data={
                "asset_type": asset_type,
                "caption": caption,
                "is_cover": str(is_cover).lower(),
            },
            files={
                "file": (
                    file_name,
                    (
                        f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                        f'<rect width="10" height="10" fill="{fill}"/>'
                        "</svg>"
                    ).encode("utf-8"),
                    "image/svg+xml",
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()


if __name__ == "__main__":
    unittest.main()
