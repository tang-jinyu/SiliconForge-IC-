from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4


TaskAssetType = Literal["board_photo", "waveform_capture", "log_snapshot", "artifact_preview"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TaskAssetRecord:
    asset_id: str
    task_id: str
    asset_type: TaskAssetType
    file_name: str
    stored_name: str
    content_type: str
    created_at: str
    caption: str = ""
    is_cover: bool = False

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "asset_id": self.asset_id,
            "task_id": self.task_id,
            "asset_type": self.asset_type,
            "file_name": self.file_name,
            "stored_name": self.stored_name,
            "content_type": self.content_type,
            "created_at": self.created_at,
            "caption": self.caption,
            "is_cover": self.is_cover,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str | bool]) -> "TaskAssetRecord":
        return cls(
            asset_id=str(payload["asset_id"]),
            task_id=str(payload["task_id"]),
            asset_type=str(payload["asset_type"]),
            file_name=str(payload["file_name"]),
            stored_name=str(payload["stored_name"]),
            content_type=str(payload.get("content_type") or "application/octet-stream"),
            created_at=str(payload.get("created_at") or _utcnow_iso()),
            caption=str(payload.get("caption") or ""),
            is_cover=bool(payload.get("is_cover", False)),
        )


class TaskAssetStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_assets(self, task_id: str) -> list[TaskAssetRecord]:
        index_path = self._index_path(task_id)
        if not index_path.exists():
            return []
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        return [TaskAssetRecord.from_dict(item) for item in payload.get("assets", [])]

    def add_asset(
        self,
        *,
        task_id: str,
        asset_type: TaskAssetType,
        file_name: str,
        content_type: str,
        data: bytes,
        caption: str = "",
        is_cover: bool = False,
    ) -> TaskAssetRecord:
        task_dir = self._task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(file_name or "upload.bin").suffix or ".bin"
        asset_id = uuid4().hex
        stored_name = f"{asset_id}{suffix.lower()}"
        (task_dir / stored_name).write_bytes(data)

        assets = self.list_assets(task_id)
        if is_cover or not any(asset.is_cover for asset in assets):
            assets = [self._replace_cover_flag(asset, False) for asset in assets]
            is_cover = True

        record = TaskAssetRecord(
            asset_id=asset_id,
            task_id=task_id,
            asset_type=asset_type,
            file_name=file_name or stored_name,
            stored_name=stored_name,
            content_type=content_type or "application/octet-stream",
            created_at=_utcnow_iso(),
            caption=caption.strip(),
            is_cover=is_cover,
        )
        assets.append(record)
        self._save(task_id, assets)
        return record

    def set_cover(self, task_id: str, asset_id: str) -> TaskAssetRecord:
        assets = self.list_assets(task_id)
        if not assets:
            raise ValueError(f"No assets found for task {task_id}.")

        updated: list[TaskAssetRecord] = []
        selected: TaskAssetRecord | None = None
        for asset in assets:
            flagged = self._replace_cover_flag(asset, asset.asset_id == asset_id)
            updated.append(flagged)
            if flagged.asset_id == asset_id:
                selected = flagged

        if selected is None:
            raise ValueError(f"Asset {asset_id} not found for task {task_id}.")

        self._save(task_id, updated)
        return selected

    def build_asset_url(self, record: TaskAssetRecord) -> str:
        return f"/task-assets/{record.task_id}/{record.stored_name}"

    def get_cover_asset(self, task_id: str) -> TaskAssetRecord | None:
        assets = self.list_assets(task_id)
        for asset in assets:
            if asset.is_cover:
                return asset
        return assets[0] if assets else None

    def _save(self, task_id: str, assets: list[TaskAssetRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"assets": [asset.to_dict() for asset in assets]}
        self._index_path(task_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _task_dir(self, task_id: str) -> Path:
        return self.root / task_id

    def _index_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "index.json"

    @staticmethod
    def _replace_cover_flag(asset: TaskAssetRecord, is_cover: bool) -> TaskAssetRecord:
        return TaskAssetRecord(
            asset_id=asset.asset_id,
            task_id=asset.task_id,
            asset_type=asset.asset_type,
            file_name=asset.file_name,
            stored_name=asset.stored_name,
            content_type=asset.content_type,
            created_at=asset.created_at,
            caption=asset.caption,
            is_cover=is_cover,
        )
