import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from digital_ic_agent.api import build_app
from digital_ic_agent.task_models import AgentTaskRequest
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService


class ArtifactWorkspaceApiTest(unittest.TestCase):
    def test_edit_and_download_structured_delivery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = AgentTaskService(repo_root=root, queue=FileTaskQueue(root / ".agent_queue"))
            output_dir = root / "runs" / "demo"
            output_dir.mkdir(parents=True)
            record = service.enqueue(AgentTaskRequest(
                title="workspace demo",
                requirement_text="demo",
                output_dir=output_dir,
                dry_run=True,
            ))
            (output_dir / "rtl").mkdir()
            (output_dir / "rtl" / "rtl_code.v").write_text("module demo; endmodule\n", encoding="utf-8")

            with TestClient(build_app(service=service)) as client:
                saved = client.put(
                    f"/api/tasks/{record.task_id}/artifacts/rtl/rtl_code.v",
                    json={"content": "module demo; wire ok; endmodule\n"},
                )
                self.assertEqual(saved.status_code, 200)
                downloaded = client.get(f"/api/tasks/{record.task_id}/download")
                self.assertEqual(downloaded.status_code, 200)

            self.assertIn("wire ok", (output_dir / "rtl" / "rtl_code.v").read_text(encoding="utf-8"))
            with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
                names = set(archive.namelist())
            self.assertIn("demo/rtl/rtl_code.v", names)
            self.assertIn("demo/meta/manual_edits.json", names)


if __name__ == "__main__":
    unittest.main()
