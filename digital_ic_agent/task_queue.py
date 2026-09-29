from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .task_models import AgentTaskRecord, AgentTaskRequest


class FileTaskQueue:
    def __init__(self, queue_root: Path) -> None:
        self.queue_root = queue_root
        self.tasks_dir = self.queue_root / "tasks"

    def submit(self, request: AgentTaskRequest) -> AgentTaskRecord:
        record = AgentTaskRecord.create(request)
        self.save(record)
        return record

    def save(self, record: AgentTaskRecord) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        path = self.tasks_dir / f"{record.task_id}.json"
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, task_id: str) -> AgentTaskRecord | None:
        path = self.tasks_dir / f"{task_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AgentTaskRecord.from_dict(payload)

    def list_tasks(self) -> list[AgentTaskRecord]:
        if not self.tasks_dir.exists():
            return []

        records: list[AgentTaskRecord] = []
        for path in sorted(self.tasks_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(AgentTaskRecord.from_dict(payload))
        return sorted(records, key=lambda record: record.created_at)

    def claim_next(self, predicate: Callable[[AgentTaskRecord], bool] | None = None) -> AgentTaskRecord | None:
        for record in self.list_tasks():
            if record.status != "pending":
                continue
            if predicate is not None and not predicate(record):
                continue
            running_record = record.mark_running()
            self.save(running_record)
            return running_record
        return None
