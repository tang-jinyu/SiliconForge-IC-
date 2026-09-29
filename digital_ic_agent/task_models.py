from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from .task_kinds import DEFAULT_TASK_KIND, get_task_kind_definition


TaskStatus = Literal["pending", "running", "succeeded", "failed", "canceled"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgentTaskRequest:
    title: str
    requirement_text: str
    output_dir: Path
    task_file: Path | None = None
    mode: str = "fpga"
    dry_run: bool = False
    task_kind: str = DEFAULT_TASK_KIND
    origin: str = "cli"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_task_file(
        cls,
        task_file: Path,
        output_dir: Path,
        *,
        mode: str = "fpga",
        dry_run: bool = False,
        task_kind: str = DEFAULT_TASK_KIND,
        title: str | None = None,
        origin: str = "cli",
        metadata: dict[str, Any] | None = None,
    ) -> "AgentTaskRequest":
        requirement_text = task_file.read_text(encoding="utf-8")
        get_task_kind_definition(task_kind)
        return cls(
            title=title or task_file.stem,
            requirement_text=requirement_text,
            output_dir=output_dir,
            task_file=task_file,
            mode=mode,
            dry_run=dry_run,
            task_kind=task_kind,
            origin=origin,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "requirement_text": self.requirement_text,
            "output_dir": str(self.output_dir),
            "task_file": str(self.task_file) if self.task_file else None,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "task_kind": self.task_kind,
            "origin": self.origin,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentTaskRequest":
        task_file = payload.get("task_file")
        task_kind = payload.get("task_kind", DEFAULT_TASK_KIND)
        get_task_kind_definition(task_kind)
        return cls(
            title=payload["title"],
            requirement_text=payload["requirement_text"],
            output_dir=Path(payload["output_dir"]),
            task_file=Path(task_file) if task_file else None,
            mode=payload.get("mode", "fpga"),
            dry_run=bool(payload.get("dry_run", False)),
            task_kind=task_kind,
            origin=payload.get("origin", "cli"),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class AgentTaskRecord:
    task_id: str
    status: TaskStatus
    request: AgentTaskRequest
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    model: str | None = None
    repair_attempts: int = 0
    cancel_requested: bool = False
    cancel_requested_at: str | None = None
    cancellation_stage: str | None = None

    @classmethod
    def create(cls, request: AgentTaskRequest, *, task_id: str | None = None) -> "AgentTaskRecord":
        return cls(
            task_id=task_id or uuid4().hex,
            status="pending",
            request=request,
            created_at=_utcnow_iso(),
        )

    def mark_running(self) -> "AgentTaskRecord":
        return replace(
            self,
            status="running",
            started_at=self.started_at or _utcnow_iso(),
            finished_at=None,
            error=None if not self.cancel_requested else self.error,
            cancellation_stage=None,
        )

    def mark_succeeded(self, *, model: str | None, repair_attempts: int) -> "AgentTaskRecord":
        return replace(
            self,
            status="succeeded",
            finished_at=_utcnow_iso(),
            error=None,
            model=model,
            repair_attempts=repair_attempts,
            cancel_requested=False,
            cancel_requested_at=None,
            cancellation_stage=None,
        )

    def mark_failed(self, *, error: str, model: str | None) -> "AgentTaskRecord":
        return replace(
            self,
            status="failed",
            finished_at=_utcnow_iso(),
            error=error,
            model=model,
            cancel_requested=False,
            cancel_requested_at=None,
            cancellation_stage=None,
        )

    def request_cancel(self) -> "AgentTaskRecord":
        if self.cancel_requested:
            return self
        return replace(
            self,
            cancel_requested=True,
            cancel_requested_at=_utcnow_iso(),
            error="Cancellation requested by user.",
        )

    def mark_canceled(self, *, reason: str | None = None, stage: str | None = None) -> "AgentTaskRecord":
        return replace(
            self,
            status="canceled",
            finished_at=_utcnow_iso(),
            error=reason or "Canceled by user.",
            cancel_requested=True,
            cancel_requested_at=self.cancel_requested_at or _utcnow_iso(),
            cancellation_stage=stage,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "request": self.request.to_dict(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "model": self.model,
            "repair_attempts": self.repair_attempts,
            "cancel_requested": self.cancel_requested,
            "cancel_requested_at": self.cancel_requested_at,
            "cancellation_stage": self.cancellation_stage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentTaskRecord":
        return cls(
            task_id=payload["task_id"],
            status=payload["status"],
            request=AgentTaskRequest.from_dict(payload["request"]),
            created_at=payload["created_at"],
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            error=payload.get("error"),
            model=payload.get("model"),
            repair_attempts=int(payload.get("repair_attempts", 0)),
            cancel_requested=bool(payload.get("cancel_requested", False)),
            cancel_requested_at=payload.get("cancel_requested_at"),
            cancellation_stage=payload.get("cancellation_stage"),
        )


@dataclass(frozen=True)
class AgentTaskExecution:
    record: AgentTaskRecord
    workflow_state: dict[str, Any]
    manifest: dict[str, Any]
