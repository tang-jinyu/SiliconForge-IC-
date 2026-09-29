from __future__ import annotations

import difflib
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import quote

from pydantic import BaseModel, Field

from .fpga_skills import FPGA_SKILLS
from .artifact_layout import resolve_delivery_path, structured_path
from .task_assets import TaskAssetStore
from .task_kinds import get_task_kind_definition
from .task_models import AgentTaskRecord


ARTIFACT_PROGRESS_STEPS = [
    (structured_path("requirement_analysis.json"), "需求分析"),
    (structured_path("architecture_design.json"), "架构设计"),
    (structured_path("specification.md"), "规格生成"),
    (structured_path("rtl_code.v"), "RTL 生成"),
    (structured_path("testbench.v"), "TB 生成"),
    (structured_path("eda_result.json"), "EDA 检查"),
    (structured_path("review.json"), "审查输出"),
    (structured_path("delivery_report.md"), "交付说明书"),
]

PREVIEW_TEXT_LIMIT = 4000

ARTIFACT_PREVIEW_DEFINITIONS = [
    (structured_path("task_input.md"), "任务输入", "markdown", "text/markdown"),
    (structured_path("llm_trace.json"), "LLM 执行诊断", "json", "application/json"),
    (structured_path("benchmark_score.json"), "Benchmark 分数", "json", "application/json"),
    (structured_path("requirement_analysis.json"), "需求分析", "json", "application/json"),
    (structured_path("architecture_design.json"), "架构设计", "json", "application/json"),
    (structured_path("specification.md"), "规格文档", "markdown", "text/markdown"),
    (structured_path("rtl_code.v"), "RTL 代码", "verilog", "text/plain"),
    (structured_path("testbench.v"), "测试平台代码", "verilog", "text/plain"),
    (structured_path("eda_result.json"), "EDA 结果", "json", "application/json"),
    (structured_path("blind_eda_result.json"), "隐藏 Oracle 验证结果", "json", "application/json"),
    (structured_path("feedback_report.json"), "反馈归档", "json", "application/json"),
    (structured_path("feedback_memory_snapshot.json"), "反馈记忆快照", "json", "application/json"),
    (structured_path("skill_card.json"), "技能说明卡", "json", "application/json"),
    (structured_path("security_report.json"), "技能安全报告", "json", "application/json"),
    (structured_path("review.json"), "审查输出", "json", "application/json"),
    (structured_path("delivery_report.md"), "最终交付说明书", "markdown", "text/markdown"),
    (structured_path("run_manifest.json"), "运行清单", "json", "application/json"),
]

LOG_PREVIEW_DEFINITIONS = [
    (structured_path("simulation.log"), "仿真日志", "log", "text/plain"),
    (structured_path("yosys.log"), "综合日志", "log", "text/plain"),
    (structured_path("repair_response.md"), "修复输出", "markdown", "text/markdown"),
    (structured_path("repair_history.json"), "修复历史", "json", "application/json"),
]


class TaskProgressView(BaseModel):
    completed_steps: int
    total_steps: int
    percent: int
    current_stage: str
    stage_label: str


class TaskStatusView(BaseModel):
    task_id: str
    title: str
    task_kind: str
    task_kind_title: str
    status: str
    origin: str
    mode: str
    dry_run: bool
    model: str | None
    output_dir: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    error: str | None
    cancel_requested: bool = False
    cancel_requested_at: str | None = None
    cancellation_stage: str | None = None


class TaskPreviewFileView(BaseModel):
    preview_id: str
    category: str
    file_name: str
    relative_path: str
    title: str
    language: str
    content_type: str
    size_bytes: int
    updated_at: str
    preview_text: str
    truncated: bool
    raw_url: str


class TaskDiffPreviewView(BaseModel):
    diff_id: str
    category: str
    file_name: str
    relative_path: str
    title: str
    source_task_id: str
    source_task_title: str
    current_raw_url: str
    source_raw_url: str
    preview_text: str
    truncated: bool


class TaskEDASummaryView(BaseModel):
    available: bool
    tool_backend: str | None = None
    top_module: str | None = None
    overall_pass: bool | None = None
    simulation_passed: bool | None = None
    synthesis_passed: bool | None = None
    interface_contract_failed: bool = False
    testbench_precheck_failed: bool = False
    missing_module_definitions: list[str] = Field(default_factory=list)
    precheck_issues: list[str] = Field(default_factory=list)


class RepairHistoryEntryView(BaseModel):
    attempt: int
    label: str
    summary: str
    source: str


class TaskCoverAssetView(BaseModel):
    asset_id: str
    asset_type: str
    caption: str
    content_type: str
    created_at: str
    is_cover: bool
    file_name: str
    url: str


class TaskGalleryItemView(BaseModel):
    task_id: str
    title: str
    task_kind_title: str
    image_url: str | None = None
    caption: str
    asset_type: str | None = None
    fallback_scene_url: str | None = None


class TaskSummaryView(BaseModel):
    status: TaskStatusView
    progress: TaskProgressView
    eda_summary: TaskEDASummaryView
    repair_history: list[RepairHistoryEntryView] = Field(default_factory=list)
    cover_assets: list[TaskCoverAssetView] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)


class TaskDetailView(BaseModel):
    task_id: str
    assets: list[TaskCoverAssetView] = Field(default_factory=list)
    waveform_assets: list[TaskCoverAssetView] = Field(default_factory=list)
    artifact_previews: list[TaskPreviewFileView] = Field(default_factory=list)
    log_previews: list[TaskPreviewFileView] = Field(default_factory=list)
    diff_previews: list[TaskDiffPreviewView] = Field(default_factory=list)
    llm_execution: "TaskLLMExecutionView | None" = None
    quality_panel: TaskQualityPanelView | None = None


class TaskLLMCapabilityProbeView(BaseModel):
    base_url: str | None = None
    checked_at: str | None = None
    supports_responses_background: bool | None = None
    source: str | None = None
    detail: str | None = None


class TaskLLMExecutionView(BaseModel):
    transport: str | None = None
    transport_requested: str | None = None
    response_id: str | None = None
    response_status: str | None = None
    last_operation_label: str | None = None
    provider_cancel_requested: bool = False
    provider_cancel_completed: bool = False
    last_error: str | None = None
    updated_at: str | None = None
    capability_probe: TaskLLMCapabilityProbeView | None = None


class TaskQualityCountView(BaseModel):
    key: str
    label: str
    count: int


class TaskBenchmarkCheckView(BaseModel):
    name: str
    weight: int
    passed: bool
    detail: str


class TaskBenchmarkScoreView(BaseModel):
    available: bool
    case_id: str | None = None
    title: str | None = None
    score: int | None = None
    passed: bool | None = None
    task_status: str | None = None
    repair_attempts: int | None = None
    feedback_tags: list[str] = Field(default_factory=list)
    feedback_fingerprints: list[str] = Field(default_factory=list)
    checks: list[TaskBenchmarkCheckView] = Field(default_factory=list)


class TaskFeedbackFingerprintView(BaseModel):
    key: str
    title: str
    skill_key: str
    evidence: str
    summary: str


class TaskFeedbackReportView(BaseModel):
    available: bool
    outcome: str | None = None
    error_tags: list[str] = Field(default_factory=list)
    skill_categories: list[str] = Field(default_factory=list)
    fingerprint_keys: list[str] = Field(default_factory=list)
    recommended_guardrails: list[str] = Field(default_factory=list)
    semantic_fingerprints: list[TaskFeedbackFingerprintView] = Field(default_factory=list)


class TaskFeedbackMemoryView(BaseModel):
    available: bool
    updated_at: str | None = None
    entry_count: int = 0
    top_tags: list[TaskQualityCountView] = Field(default_factory=list)
    top_skill_categories: list[TaskQualityCountView] = Field(default_factory=list)
    top_fingerprints: list[TaskQualityCountView] = Field(default_factory=list)
    recent_guardrails: list[str] = Field(default_factory=list)


class TaskSecurityCheckView(BaseModel):
    name: str
    status: str
    detail: str
    evidence: list[str] = Field(default_factory=list)


class TaskSkillGovernanceView(BaseModel):
    available: bool
    name: str | None = None
    version: str | None = None
    owner: str | None = None
    security_verdict: str | None = None
    package_digest: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    allowed_eda_tools: list[str] = Field(default_factory=list)
    checks: list[TaskSecurityCheckView] = Field(default_factory=list)
    verified_skills_alignment: dict[str, dict[str, str]] = Field(default_factory=dict)


class TaskQualityPanelView(BaseModel):
    benchmark: TaskBenchmarkScoreView
    feedback_report: TaskFeedbackReportView
    feedback_memory: TaskFeedbackMemoryView
    skill_governance: TaskSkillGovernanceView


class TaskSummaryService:
    def __init__(
        self,
        asset_store: TaskAssetStore | None = None,
        task_lookup: Callable[[str], AgentTaskRecord | None] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.asset_store = asset_store
        self.task_lookup = task_lookup
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]

    def build_summary(self, record: AgentTaskRecord) -> TaskSummaryView:
        task_kind_definition = get_task_kind_definition(record.request.task_kind)
        output_dir = record.request.output_dir

        return TaskSummaryView(
            status=TaskStatusView(
                task_id=record.task_id,
                title=record.request.title,
                task_kind=record.request.task_kind,
                task_kind_title=task_kind_definition.title,
                status=record.status,
                origin=record.request.origin,
                mode=record.request.mode,
                dry_run=record.request.dry_run,
                model=record.model,
                output_dir=str(output_dir.resolve()),
                created_at=record.created_at,
                started_at=record.started_at,
                finished_at=record.finished_at,
                error=record.error,
                cancel_requested=record.cancel_requested,
                cancel_requested_at=record.cancel_requested_at,
                cancellation_stage=record.cancellation_stage,
            ),
            progress=self._build_progress(record, output_dir),
            eda_summary=self._build_eda_summary(output_dir),
            repair_history=self._build_repair_history(output_dir, record),
            cover_assets=self._build_cover_assets(record.task_id),
            available_actions=self._build_available_actions(record),
        )

    def build_many(self, records: list[AgentTaskRecord]) -> list[TaskSummaryView]:
        return [self.build_summary(record) for record in sorted(records, key=lambda item: item.created_at, reverse=True)]

    def build_gallery(self, records: list[AgentTaskRecord]) -> list[TaskGalleryItemView]:
        items: list[TaskGalleryItemView] = []
        for record in sorted(records, key=lambda item: item.created_at, reverse=True):
            definition = get_task_kind_definition(record.request.task_kind)
            cover_assets = self._build_cover_assets(record.task_id)
            cover_asset = next((asset for asset in cover_assets if asset.is_cover), None)
            items.append(
                TaskGalleryItemView(
                    task_id=record.task_id,
                    title=record.request.title,
                    task_kind_title=definition.title,
                    image_url=cover_asset.url if cover_asset else None,
                    caption=(cover_asset.caption if cover_asset and cover_asset.caption else definition.gallery_caption),
                    asset_type=cover_asset.asset_type if cover_asset else None,
                    fallback_scene_url=None if cover_asset else f"/assets/scene-{(len(items) % 4) + 1}.svg",
                )
            )
        return items

    def build_detail(self, record: AgentTaskRecord) -> TaskDetailView:
        return TaskDetailView(
            task_id=record.task_id,
            assets=self._build_cover_assets(record.task_id),
            waveform_assets=self._build_waveform_assets(record.task_id),
            artifact_previews=self._build_file_previews(record, "artifact"),
            log_previews=self._build_file_previews(record, "log"),
            diff_previews=self._build_diff_previews(record),
            llm_execution=self._build_llm_execution(record),
            quality_panel=self._build_quality_panel(record),
        )

    def list_artifact_previews(self, record: AgentTaskRecord) -> list[TaskPreviewFileView]:
        return self._build_file_previews(record, "artifact")

    def list_log_previews(self, record: AgentTaskRecord) -> list[TaskPreviewFileView]:
        return self._build_file_previews(record, "log")

    def resolve_preview_path(
        self,
        record: AgentTaskRecord,
        category: Literal["artifact", "log"],
        file_name: str,
    ) -> Path:
        normalized = file_name.replace("\\", "/").lstrip("/")
        if ".." in Path(normalized).parts or normalized in {".", ".."}:
            raise ValueError(f"Unsupported {category} file name: {file_name}")

        definition_map = self._preview_definition_map(category)
        definition = definition_map.get(normalized) or definition_map.get(structured_path(normalized))
        if definition is None:
            raise ValueError(f"Unsupported {category} file name: {file_name}")

        path = resolve_delivery_path(record.request.output_dir, definition[0]).resolve()
        output_root = record.request.output_dir.resolve()
        if not path.is_relative_to(output_root):
            raise ValueError(f"Unsupported {category} file path: {file_name}")
        if not path.exists():
            raise FileNotFoundError(file_name)
        return path

    def _build_progress(self, record: AgentTaskRecord, output_dir: Path) -> TaskProgressView:
        if record.status == "pending":
            return TaskProgressView(
                completed_steps=0,
                total_steps=len(ARTIFACT_PROGRESS_STEPS),
                percent=0,
                current_stage="queued",
                stage_label="等待执行",
            )

        completed_steps = 0
        current_label = "初始化"
        current_stage = "bootstrapping"
        for file_name, label in ARTIFACT_PROGRESS_STEPS:
            if resolve_delivery_path(output_dir, file_name).exists():
                completed_steps += 1
                current_label = label
                current_stage = file_name
            else:
                current_label = label
                current_stage = file_name
                break

        total_steps = len(ARTIFACT_PROGRESS_STEPS)
        percent = int((completed_steps / total_steps) * 100) if total_steps else 0
        if record.status == "running" and completed_steps < total_steps:
            percent = max(percent, 5)
            if record.cancel_requested:
                current_stage = "cancel_requested"
                current_label = "取消中"
        if record.status == "succeeded":
            percent = 100
            current_stage = "completed"
            current_label = "已完成"
        elif record.status == "canceled":
            current_stage = "canceled"
            current_label = "已取消"
        elif record.status == "failed":
            current_stage = "failed"
            current_label = "执行失败"

        return TaskProgressView(
            completed_steps=completed_steps,
            total_steps=total_steps,
            percent=percent,
            current_stage=current_stage,
            stage_label=current_label,
        )

    def _build_eda_summary(self, output_dir: Path) -> TaskEDASummaryView:
        eda_path = resolve_delivery_path(output_dir, structured_path("eda_result.json"))
        if not eda_path.exists():
            return TaskEDASummaryView(available=False)

        payload = json.loads(eda_path.read_text(encoding="utf-8"))
        return TaskEDASummaryView(
            available=True,
            tool_backend=payload.get("tool_backend"),
            top_module=payload.get("top_module"),
            overall_pass=payload.get("overall_pass"),
            simulation_passed=payload.get("simulation_passed"),
            synthesis_passed=payload.get("synthesis_passed"),
            interface_contract_failed=bool(payload.get("interface_contract_failed")),
            testbench_precheck_failed=bool(payload.get("testbench_precheck_failed")),
            missing_module_definitions=list(payload.get("missing_module_definitions") or []),
            precheck_issues=list(payload.get("precheck_issues") or []),
        )

    def _build_repair_history(self, output_dir: Path, record: AgentTaskRecord) -> list[RepairHistoryEntryView]:
        history_path = resolve_delivery_path(output_dir, structured_path("repair_history.json"))
        if history_path.exists():
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            items = payload.get("history", payload) if isinstance(payload, dict) else payload
            return [
                RepairHistoryEntryView(
                    attempt=int(item.get("attempt", index + 1)),
                    label=str(item.get("label", f"第 {index + 1} 次修复")),
                    summary=str(item.get("summary", "")),
                    source=str(item.get("source", "workflow")),
                )
                for index, item in enumerate(items)
            ]

        repair_response_path = resolve_delivery_path(output_dir, structured_path("repair_response.md"))
        if repair_response_path.exists():
            return [
                RepairHistoryEntryView(
                    attempt=max(record.repair_attempts, 1),
                    label="最终修复输出",
                    summary=repair_response_path.read_text(encoding="utf-8")[:240].strip(),
                    source="repair_response.md",
                )
            ]
        return []

    def _build_cover_assets(self, task_id: str) -> list[TaskCoverAssetView]:
        if self.asset_store is None:
            return []
        return [
            TaskCoverAssetView(
                asset_id=asset.asset_id,
                asset_type=asset.asset_type,
                caption=asset.caption,
                content_type=asset.content_type,
                created_at=asset.created_at,
                is_cover=asset.is_cover,
                file_name=asset.file_name,
                url=self.asset_store.build_asset_url(asset),
            )
            for asset in self.asset_store.list_assets(task_id)
        ]

    def _build_waveform_assets(self, task_id: str) -> list[TaskCoverAssetView]:
        return [asset for asset in self._build_cover_assets(task_id) if asset.asset_type == "waveform_capture"]

    def _build_llm_execution(self, record: AgentTaskRecord) -> TaskLLMExecutionView | None:
        trace_path = resolve_delivery_path(record.request.output_dir, structured_path("llm_trace.json"))
        if not trace_path.exists():
            return None

        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        capability_payload = payload.get("capability_probe")
        capability = None
        if isinstance(capability_payload, dict):
            capability = TaskLLMCapabilityProbeView(
                base_url=capability_payload.get("base_url"),
                checked_at=capability_payload.get("checked_at"),
                supports_responses_background=capability_payload.get("supports_responses_background"),
                source=capability_payload.get("source"),
                detail=capability_payload.get("detail"),
            )

        return TaskLLMExecutionView(
            transport=payload.get("transport"),
            transport_requested=payload.get("transport_requested"),
            response_id=payload.get("response_id"),
            response_status=payload.get("response_status"),
            last_operation_label=payload.get("last_operation_label"),
            provider_cancel_requested=bool(payload.get("provider_cancel_requested", False)),
            provider_cancel_completed=bool(payload.get("provider_cancel_completed", False)),
            last_error=payload.get("last_error"),
            updated_at=payload.get("updated_at"),
            capability_probe=capability,
        )

    def _build_quality_panel(self, record: AgentTaskRecord) -> TaskQualityPanelView:
        return TaskQualityPanelView(
            benchmark=self._build_benchmark_score(record),
            feedback_report=self._build_feedback_report(record),
            feedback_memory=self._build_feedback_memory(),
            skill_governance=self._build_skill_governance(record),
        )

    def _build_skill_governance(self, record: AgentTaskRecord) -> TaskSkillGovernanceView:
        card_path = resolve_delivery_path(record.request.output_dir, structured_path("skill_card.json"))
        report_path = resolve_delivery_path(record.request.output_dir, structured_path("security_report.json"))
        if not card_path.exists() or not report_path.exists():
            return TaskSkillGovernanceView(available=False)

        card = json.loads(card_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        execution_boundary = dict(card.get("execution_boundary") or {})
        integrity = dict(card.get("integrity") or {})
        alignment = dict(card.get("verified_skills_alignment") or {})
        return TaskSkillGovernanceView(
            available=True,
            name=card.get("display_name") or card.get("name"),
            version=card.get("version"),
            owner=card.get("owner"),
            security_verdict=report.get("verdict"),
            package_digest=integrity.get("package_digest"),
            capabilities=list(card.get("capabilities") or []),
            allowed_eda_tools=list(execution_boundary.get("allowed_eda_tools") or []),
            verified_skills_alignment={
                str(key): {
                    "status": str((value or {}).get("status", "unknown")),
                    "evidence": str((value or {}).get("evidence", "")),
                }
                for key, value in alignment.items()
                if isinstance(value, dict)
            },
            checks=[
                TaskSecurityCheckView(
                    name=str(item.get("name", "")),
                    status=str(item.get("status", "unknown")),
                    detail=str(item.get("detail", "")),
                    evidence=list(item.get("evidence") or []),
                )
                for item in report.get("checks") or []
            ],
        )

    def _build_benchmark_score(self, record: AgentTaskRecord) -> TaskBenchmarkScoreView:
        score_path = resolve_delivery_path(record.request.output_dir, structured_path("benchmark_score.json"))
        if not score_path.exists():
            return TaskBenchmarkScoreView(available=False)

        payload = json.loads(score_path.read_text(encoding="utf-8"))
        return TaskBenchmarkScoreView(
            available=True,
            case_id=payload.get("case_id"),
            title=payload.get("title"),
            score=payload.get("score"),
            passed=payload.get("passed"),
            task_status=payload.get("task_status"),
            repair_attempts=payload.get("repair_attempts"),
            feedback_tags=list(payload.get("feedback_tags") or []),
            feedback_fingerprints=list(payload.get("feedback_fingerprints") or []),
            checks=[
                TaskBenchmarkCheckView(
                    name=str(item.get("name", "")),
                    weight=int(item.get("weight", 0)),
                    passed=bool(item.get("passed")),
                    detail=str(item.get("detail", "")),
                )
                for item in payload.get("checks") or []
            ],
        )

    def _build_feedback_report(self, record: AgentTaskRecord) -> TaskFeedbackReportView:
        report_path = resolve_delivery_path(record.request.output_dir, structured_path("feedback_report.json"))
        if not report_path.exists():
            return TaskFeedbackReportView(available=False)

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return TaskFeedbackReportView(
            available=True,
            outcome=payload.get("outcome"),
            error_tags=list(payload.get("error_tags") or []),
            skill_categories=list(payload.get("skill_categories") or []),
            fingerprint_keys=list(payload.get("fingerprint_keys") or []),
            recommended_guardrails=list(payload.get("recommended_guardrails") or []),
            semantic_fingerprints=[
                TaskFeedbackFingerprintView(
                    key=str(item.get("key", "")),
                    title=str(item.get("title", "")),
                    skill_key=str(item.get("skill_key", "")),
                    evidence=str(item.get("evidence", "")),
                    summary=str(item.get("summary", "")),
                )
                for item in payload.get("semantic_fingerprints") or []
            ],
        )

    def _build_feedback_memory(self) -> TaskFeedbackMemoryView:
        memory_path = self.repo_root / "project_prompt" / "output" / "fpga_feedback_memory.json"
        if not memory_path.exists():
            return TaskFeedbackMemoryView(available=False)

        payload = json.loads(memory_path.read_text(encoding="utf-8"))
        skill_title_map = {skill.key: skill.title for skill in FPGA_SKILLS}
        return TaskFeedbackMemoryView(
            available=True,
            updated_at=payload.get("updated_at"),
            entry_count=len(payload.get("entries") or []),
            top_tags=self._build_count_views(payload.get("tag_counts") or {}),
            top_skill_categories=self._build_count_views(payload.get("skill_counts") or {}, label_map=skill_title_map),
            top_fingerprints=self._build_count_views(payload.get("fingerprint_counts") or {}),
            recent_guardrails=self._recent_guardrails_from_memory(payload),
        )

    @staticmethod
    def _build_count_views(counts: dict[str, int], *, label_map: dict[str, str] | None = None) -> list[TaskQualityCountView]:
        sorted_items = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        return [
            TaskQualityCountView(
                key=str(key),
                label=(label_map or {}).get(str(key), str(key)),
                count=int(count),
            )
            for key, count in sorted_items[:5]
        ]

    @staticmethod
    def _recent_guardrails_from_memory(payload: dict[str, object]) -> list[str]:
        guardrails: list[str] = []
        for entry in reversed(list(payload.get("entries") or [])):
            if not isinstance(entry, dict):
                continue
            for item in entry.get("recommended_guardrails") or []:
                text = str(item)
                if text and text not in guardrails:
                    guardrails.append(text)
            if len(guardrails) >= 6:
                break
        return guardrails[:6]

    @staticmethod
    def _build_available_actions(record: AgentTaskRecord) -> list[str]:
        actions = ["detail"]
        if record.status == "pending":
            actions.append("cancel")
        elif record.status == "running" and not record.cancel_requested:
            actions.append("cancel")
        elif record.status in {"failed", "canceled", "succeeded"}:
            actions.append("retry")
        return actions

    def _build_diff_previews(self, record: AgentTaskRecord) -> list[TaskDiffPreviewView]:
        source_record = self._resolve_retry_source(record)
        if source_record is None:
            return []

        previews: list[TaskDiffPreviewView] = []
        for category in ("artifact", "log"):
            for file_name, title, _language, _content_type in self._preview_definitions(category):
                current_path = resolve_delivery_path(record.request.output_dir, file_name)
                source_path = resolve_delivery_path(source_record.request.output_dir, file_name)
                if not current_path.exists() or not source_path.exists():
                    continue

                current_text = current_path.read_text(encoding="utf-8", errors="replace")
                source_text = source_path.read_text(encoding="utf-8", errors="replace")
                diff_text = "".join(
                    difflib.unified_diff(
                        source_text.splitlines(True),
                        current_text.splitlines(True),
                        fromfile=f"{source_record.task_id}/{file_name}",
                        tofile=f"{record.task_id}/{file_name}",
                        n=3,
                    )
                )
                if not diff_text:
                    continue

                truncated = len(diff_text) > PREVIEW_TEXT_LIMIT
                preview_text = diff_text[:PREVIEW_TEXT_LIMIT]
                if truncated:
                    preview_text += "\n\n... (truncated)"

                previews.append(
                    TaskDiffPreviewView(
                        diff_id=f"{category}:{file_name}",
                        category=category,
                        file_name=Path(file_name).name,
                        relative_path=file_name,
                        title=title,
                        source_task_id=source_record.task_id,
                        source_task_title=source_record.request.title,
                        current_raw_url=self._build_preview_url(record.task_id, category, file_name),
                        source_raw_url=self._build_preview_url(source_record.task_id, category, file_name),
                        preview_text=preview_text,
                        truncated=truncated,
                    )
                )

        return previews

    def _resolve_retry_source(self, record: AgentTaskRecord) -> AgentTaskRecord | None:
        if self.task_lookup is None:
            return None
        retry_of = record.request.metadata.get("retry_of")
        if not isinstance(retry_of, str) or not retry_of.strip():
            return None
        return self.task_lookup(retry_of)

    def _build_file_previews(
        self,
        record: AgentTaskRecord,
        category: Literal["artifact", "log"],
    ) -> list[TaskPreviewFileView]:
        previews: list[TaskPreviewFileView] = []
        for file_name, title, language, content_type in self._preview_definitions(category):
            path = resolve_delivery_path(record.request.output_dir, file_name)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            truncated = len(text) > PREVIEW_TEXT_LIMIT
            preview_text = text[:PREVIEW_TEXT_LIMIT]
            if truncated:
                preview_text += "\n\n... (truncated)"
            previews.append(
                TaskPreviewFileView(
                    preview_id=f"{category}:{file_name}",
                    category=category,
                    file_name=Path(file_name).name,
                    relative_path=file_name,
                    title=title,
                    language=language,
                    content_type=content_type,
                    size_bytes=path.stat().st_size,
                    updated_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                    preview_text=preview_text,
                    truncated=truncated,
                    raw_url=self._build_preview_url(record.task_id, category, file_name),
                )
            )
        return previews

    @staticmethod
    def _preview_definitions(category: Literal["artifact", "log"]) -> list[tuple[str, str, str, str]]:
        return ARTIFACT_PREVIEW_DEFINITIONS if category == "artifact" else LOG_PREVIEW_DEFINITIONS

    def _preview_definition_map(
        self,
        category: Literal["artifact", "log"],
    ) -> dict[str, tuple[str, str, str, str]]:
        return {item[0]: item for item in self._preview_definitions(category)}

    @staticmethod
    def _build_preview_url(task_id: str, category: Literal["artifact", "log"], file_name: str) -> str:
        route_segment = "artifacts" if category == "artifact" else "logs"
        route_file_name = file_name
        if category == "log" and route_file_name.startswith("logs/"):
            route_file_name = route_file_name.removeprefix("logs/")
        return f"/api/tasks/{task_id}/{route_segment}/{quote(route_file_name, safe='/')}"
