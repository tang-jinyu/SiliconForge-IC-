from __future__ import annotations

import asyncio
import io
import json
import os
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .environment import load_project_environment

load_project_environment()

from .auth import AUTH_SUBJECT_METADATA_KEY, AuthManager, AuthSession
from .artifact_layout import EDITABLE_DELIVERY_PATHS, resolve_delivery_path, structured_path
from .benchmark_runner import run_benchmark_suite
from .code_utils import sanitize_verilog_rtl, sanitize_verilog_testbench
from .prechecks import load_interface_contract, run_prechecked_eda
from .task_assets import TaskAssetStore
from .task_kinds import DEFAULT_TASK_KIND, get_task_kind_definition, list_task_kind_definitions
from .task_models import AgentTaskRecord
from .task_models import AgentTaskRequest
from .task_service import AgentTaskService
from .task_views import TaskSummaryService
from .template_library import TemplateLibrary
from .runtime_info import build_runtime_report


class TaskSubmissionPayload(BaseModel):
    title: str | None = None
    task_kind: str = DEFAULT_TASK_KIND
    mode: str = "fpga"
    dry_run: bool = False
    # GUI/API default: a submitted task must actually run. Queue mode remains
    # available for deployments that have a dedicated worker.
    execution: Literal["queue", "sync"] = "sync"
    output_dir: str | None = None
    task_file: str | None = None
    requirement_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> "TaskSubmissionPayload":
        get_task_kind_definition(self.task_kind)
        workflow_backed_kinds = {
            "digital_ic_workflow",
            "rtl_module_generation",
            "tb_repair",
        }
        if not self.task_file and not self.requirement_text and self.task_kind in workflow_backed_kinds:
            if self.title and self.title.strip():
                self.requirement_text = self.title.strip()
            else:
                raise ValueError("Paste the problem statement before starting the workflow.")
        return self


class LoginPayload(BaseModel):
    display_name: str
    password: str


class SessionLLMConfigPayload(BaseModel):
    api_key: str
    base_url: str | None = None
    model: str | None = None
    llm_transport: Literal["auto", "chat", "responses_background"] = "auto"
    temperature: float | None = None


class ArtifactEditPayload(BaseModel):
    content: str = Field(max_length=1_000_000)


class TemplateInstantiatePayload(BaseModel):
    title: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class TemplateSavePayload(BaseModel):
    title: str | None = None


def build_app(
    *,
    service: AgentTaskService | None = None,
    asset_store: TaskAssetStore | None = None,
    summary_service: TaskSummaryService | None = None,
    auth_manager: AuthManager | None = None,
) -> FastAPI:
    auth_manager = auth_manager or AuthManager.from_env()
    service = service or AgentTaskService(llm_config_resolver=auth_manager.resolve_runtime_llm_config)
    service.llm_config_resolver = auth_manager.resolve_runtime_llm_config
    asset_store = asset_store or TaskAssetStore(service.repo_root / ".agent_queue" / "assets")
    summary_service = summary_service or TaskSummaryService(asset_store=asset_store, task_lookup=service.get_task)
    template_library = TemplateLibrary(service.repo_root)

    app = FastAPI(
        title="Digital IC Agent API",
        version="0.2.0",
        summary="Task-service-backed API and UI for the Digital IC Agent",
    )

    web_root = Path(__file__).resolve().parent / "web"
    assets_root = web_root / "assets"
    pictures_root = service.repo_root / "picture"
    if assets_root.exists():
        app.mount("/assets", StaticFiles(directory=assets_root), name="assets")
    if pictures_root.exists():
        app.mount("/pictures", StaticFiles(directory=pictures_root), name="pictures")
    if asset_store.root.exists() or not asset_store.root.exists():
        asset_store.root.mkdir(parents=True, exist_ok=True)
        app.mount("/task-assets", StaticFiles(directory=asset_store.root), name="task-assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(
            web_root / "styles.css",
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/app.js")
    def script() -> FileResponse:
        return FileResponse(
            web_root / "app.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def runtime(request: Request) -> dict[str, Any]:
        _require_session_if_enabled(auth_manager, request)
        return build_runtime_report(service.repo_root)

    @app.get("/api/auth/session")
    def auth_session(request: Request) -> dict[str, Any]:
        return auth_manager.build_session_payload(auth_manager.read_session(request))

    @app.post("/api/auth/login")
    def login(payload: LoginPayload, request: Request, response: Response) -> dict[str, Any]:
        existing_session = auth_manager.read_session(request)
        session, token = auth_manager.login(
            display_name=payload.display_name,
            password=payload.password,
            existing_session=existing_session,
        )
        response.set_cookie(
            key=auth_manager.cookie_name,
            value=token,
            httponly=True,
            samesite="lax",
        )
        return auth_manager.build_session_payload(session)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        session = auth_manager.read_session(request)
        auth_manager.clear_session_state(session)
        response.delete_cookie(auth_manager.cookie_name)
        return {"status": "ok"}

    @app.post("/api/auth/llm-config")
    def save_llm_config(payload: SessionLLMConfigPayload, request: Request) -> dict[str, Any]:
        if not auth_manager.enabled:
            raise HTTPException(status_code=409, detail="Login mode is not enabled on this server.")
        session = auth_manager.require_session(request)
        auth_manager.save_llm_config(
            session,
            api_key=payload.api_key,
            base_url=payload.base_url,
            model=payload.model,
            llm_transport=payload.llm_transport,
            temperature=payload.temperature,
        )
        return auth_manager.build_session_payload(session)

    @app.get("/api/task-kinds")
    def task_kinds() -> list[dict[str, str]]:
        return [definition.to_dict() for definition in list_task_kind_definitions()]

    @app.get("/api/demo/phase1")
    def phase1_demo_status(request: Request) -> dict[str, Any]:
        _require_session_if_enabled(auth_manager, request)
        return dict(getattr(app.state, "phase1_demo", {"status": "idle"}))

    @app.post("/api/demo/phase1")
    def start_phase1_demo(request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        current_thread = getattr(app.state, "phase1_demo_thread", None)
        if current_thread is not None and current_thread.is_alive():
            raise HTTPException(status_code=409, detail="阶段一演示正在运行，请在工作台查看实时进度。")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        suite_dir = service.repo_root / "benchmarks" / "phase1"
        output_dir = service.repo_root / "runs" / "phase1_gui" / run_id
        metadata_overrides: dict[str, Any] = {"phase1_gui_run_id": run_id}
        if session is not None:
            metadata_overrides[AUTH_SUBJECT_METADATA_KEY] = session.subject_id

        app.state.phase1_demo = {
            "status": "running",
            "run_id": run_id,
            "output_dir": str(output_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        def run_demo() -> None:
            try:
                report = run_benchmark_suite(
                    service=service,
                    suite_dir=suite_dir,
                    output_dir=output_dir,
                    metadata_overrides=metadata_overrides,
                )
                app.state.phase1_demo = {
                    **app.state.phase1_demo,
                    "status": "succeeded" if report["passed_cases"] == report["case_count"] else "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "case_count": report["case_count"],
                    "passed_cases": report["passed_cases"],
                    "average_score": report["average_score"],
                    "report_path": str(output_dir / "benchmark_report.json"),
                }
            except Exception as exc:
                app.state.phase1_demo = {
                    **app.state.phase1_demo,
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }

        demo_thread = threading.Thread(target=run_demo, name=f"phase1-demo-{run_id}", daemon=True)
        app.state.phase1_demo_thread = demo_thread
        demo_thread.start()
        return dict(app.state.phase1_demo)

    @app.get("/api/benchmark/competition")
    def competition_benchmark_status(request: Request) -> dict[str, Any]:
        _require_session_if_enabled(auth_manager, request)
        return dict(getattr(app.state, "competition_benchmark", {"status": "idle"}))

    @app.post("/api/benchmark/competition")
    def start_competition_benchmark(request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        _ensure_session_llm_config(auth_manager, session, dry_run=False)
        current_thread = getattr(app.state, "competition_benchmark_thread", None)
        if current_thread is not None and current_thread.is_alive():
            raise HTTPException(status_code=409, detail="模型盲测正在运行，请在工作台查看实时进度。")

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        suite_dir = service.repo_root / "benchmarks" / "blind_v1"
        output_dir = service.repo_root / "runs" / "competition_benchmark" / run_id
        metadata_overrides: dict[str, Any] = {
            "competition_benchmark_run_id": run_id,
            "blind_generation": True,
        }
        if session is not None:
            metadata_overrides[AUTH_SUBJECT_METADATA_KEY] = session.subject_id

        app.state.competition_benchmark = {
            "status": "running",
            "run_id": run_id,
            "output_dir": str(output_dir),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "case_count": len(list(suite_dir.glob("*/benchmark_case.json"))),
        }

        def run_competition_benchmark() -> None:
            try:
                report = run_benchmark_suite(
                    service=service,
                    suite_dir=suite_dir,
                    output_dir=output_dir,
                    dry_run=False,
                    metadata_overrides=metadata_overrides,
                )
                first_pass_cases = sum(
                    1
                    for result in report["results"]
                    if result.get("passed") and int(result.get("repair_attempts", 0)) == 0
                )
                repaired_pass_cases = sum(
                    1
                    for result in report["results"]
                    if result.get("passed") and int(result.get("repair_attempts", 0)) > 0
                )
                app.state.competition_benchmark = {
                    **app.state.competition_benchmark,
                    "status": "succeeded" if report["passed_cases"] == report["case_count"] else "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "passed_cases": report["passed_cases"],
                    "average_score": report["average_score"],
                    "pass_at_1_cases": first_pass_cases,
                    "pass_after_repair_cases": repaired_pass_cases,
                    "report_path": str(output_dir / "benchmark_report.json"),
                }
            except Exception as exc:
                app.state.competition_benchmark = {
                    **app.state.competition_benchmark,
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }

        benchmark_thread = threading.Thread(
            target=run_competition_benchmark,
            name=f"competition-benchmark-{run_id}",
            daemon=True,
        )
        app.state.competition_benchmark_thread = benchmark_thread
        benchmark_thread.start()
        return dict(app.state.competition_benchmark)

    @app.get("/api/dashboard")
    def dashboard(request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        return _build_dashboard_snapshot(summary_service, _list_visible_records(service, auth_manager, session))

    @app.get("/api/templates")
    def list_templates(request: Request) -> list[dict[str, Any]]:
        _require_session_if_enabled(auth_manager, request)
        return template_library.list_templates()

    @app.post("/api/templates/{template_id}/instantiate")
    def instantiate_template(
        template_id: str,
        payload: TemplateInstantiatePayload,
        request: Request,
    ) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        try:
            rendered = template_library.render(template_id, payload.parameters)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="没有找到该模板。") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        metadata: dict[str, Any] = {}
        if session is not None:
            metadata[AUTH_SUBJECT_METADATA_KEY] = session.subject_id
        execution = service.run_template(rendered, title=payload.title, metadata=metadata)
        return {
            "record": execution.record.to_dict(),
            "summary": summary_service.build_summary(execution.record).model_dump(),
            "token_usage": 0,
        }

    @app.post("/api/tasks/{task_id}/save-template")
    def save_task_as_template(
        task_id: str,
        payload: TemplateSavePayload,
        request: Request,
    ) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        if record.status != "succeeded":
            raise HTTPException(status_code=409, detail="只有成功任务才能保存为模板。")
        try:
            template = template_library.add_from_task(
                task_id=task_id,
                title=(payload.title or record.request.title).strip(),
                output_dir=record.request.output_dir,
                requirement_text=record.request.requirement_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "已加入个人模板库", "template": template}

    @app.get("/api/tasks")
    def tasks(request: Request) -> list[dict[str, Any]]:
        session = _require_session_if_enabled(auth_manager, request)
        return [
            summary.model_dump()
            for summary in summary_service.build_many(_list_visible_records(service, auth_manager, session))
        ]

    @app.get("/api/stream/tasks")
    async def stream_tasks(request: Request, once: bool = Query(default=False)) -> StreamingResponse:
        session = _require_session_if_enabled(auth_manager, request)

        async def event_generator():
            last_snapshot: dict[str, Any] | None = None
            while True:
                if await request.is_disconnected():
                    break

                snapshot = _build_dashboard_snapshot(
                    summary_service,
                    _list_visible_records(service, auth_manager, session),
                )
                if last_snapshot is None:
                    yield _format_sse_event("snapshot", snapshot)
                    last_snapshot = snapshot
                    if once:
                        break
                else:
                    for event_name, payload in _build_dashboard_events(last_snapshot, snapshot):
                        yield _format_sse_event(event_name, payload)
                    last_snapshot = snapshot
                await asyncio.sleep(1.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/tasks/{task_id}")
    def task(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        summary = summary_service.build_summary(record)
        return {
            "record": record.to_dict(),
            "summary": summary.model_dump(),
        }

    @app.get("/api/tasks/{task_id}/summary")
    def task_summary(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        return summary_service.build_summary(record).model_dump()

    @app.get("/api/tasks/{task_id}/detail")
    def task_detail(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        return {
            "record": record.to_dict(),
            "summary": summary_service.build_summary(record).model_dump(),
            "detail": summary_service.build_detail(record).model_dump(),
        }

    @app.get("/api/tasks/{task_id}/artifacts")
    def task_artifacts(task_id: str, request: Request) -> list[dict[str, Any]]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        return [item.model_dump() for item in summary_service.list_artifact_previews(record)]

    @app.get("/api/tasks/{task_id}/logs")
    def task_logs(task_id: str, request: Request) -> list[dict[str, Any]]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        return [item.model_dump() for item in summary_service.list_log_previews(record)]

    @app.get("/api/tasks/{task_id}/artifacts/{file_name:path}")
    def task_artifact_file(task_id: str, file_name: str, request: Request) -> FileResponse:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        path = _resolve_preview_or_404(summary_service, record, "artifact", file_name)
        return FileResponse(path, filename=path.name)

    @app.get("/api/tasks/{task_id}/logs/{file_name:path}")
    def task_log_file(task_id: str, file_name: str, request: Request) -> FileResponse:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        path = _resolve_preview_or_404(summary_service, record, "log", file_name)
        return FileResponse(path, filename=path.name)

    @app.put("/api/tasks/{task_id}/artifacts/{file_name:path}")
    def update_task_artifact(
        task_id: str,
        file_name: str,
        payload: ArtifactEditPayload,
        request: Request,
    ) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        normalized = structured_path(file_name)
        if normalized not in EDITABLE_DELIVERY_PATHS:
            raise HTTPException(status_code=403, detail="Only RTL, testbench, specification, and delivery report files are editable.")
        path = resolve_delivery_path(record.request.output_dir, normalized).resolve()
        output_root = record.request.output_dir.resolve()
        if not path.is_relative_to(output_root):
            raise HTTPException(status_code=400, detail="Artifact path escapes the task output directory.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload.content, encoding="utf-8")
        audit_path = record.request.output_dir / "meta" / "manual_edits.json"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_payload: list[dict[str, str]] = []
        if audit_path.exists():
            try:
                loaded = json.loads(audit_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    audit_payload = loaded
            except json.JSONDecodeError:
                audit_payload = []
        audit_payload.append({"file": normalized, "updated_at": datetime.now(timezone.utc).isoformat()})
        audit_path.write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "saved", "file_name": normalized, "size_bytes": path.stat().st_size}

    @app.post("/api/tasks/{task_id}/revalidate")
    def revalidate_task_artifacts(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        rtl_path = resolve_delivery_path(record.request.output_dir, structured_path("rtl_code.v"))
        tb_path = resolve_delivery_path(record.request.output_dir, structured_path("testbench.v"))
        if not rtl_path.exists() or not tb_path.exists():
            raise HTTPException(status_code=409, detail="RTL and testbench files are required before revalidation.")
        task_file = record.request.task_file
        result = run_prechecked_eda(
            run_dir=record.request.output_dir,
            repo_root=service.repo_root,
            rtl_code=sanitize_verilog_rtl(rtl_path.read_text(encoding="utf-8")),
            testbench_code=sanitize_verilog_testbench(tb_path.read_text(encoding="utf-8")),
            interface_contract=load_interface_contract(task_file),
        )
        eda_path = record.request.output_dir / structured_path("eda_result.json")
        sim_path = record.request.output_dir / structured_path("simulation.log")
        synth_path = record.request.output_dir / structured_path("yosys.log")
        for path in (eda_path, sim_path, synth_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        eda_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        sim_path.write_text(str(result.get("simulation_log") or ""), encoding="utf-8")
        synth_path.write_text(str(result.get("yosys_log") or ""), encoding="utf-8")
        return {"status": "validated", "eda_result": result}

    @app.get("/api/tasks/{task_id}/download")
    def download_task_delivery(task_id: str, request: Request) -> StreamingResponse:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        archive = io.BytesIO()
        output_root = record.request.output_dir.resolve()
        with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(output_root.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                bundle.write(path, arcname=f"{output_root.name}/{path.relative_to(output_root).as_posix()}")
        archive.seek(0)
        safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in record.request.title)
        return StreamingResponse(
            archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{safe_name or task_id}.zip"'},
        )

    @app.get("/api/tasks/{task_id}/assets")
    def task_assets(task_id: str, request: Request) -> list[dict[str, Any]]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        summary = summary_service.build_summary(record)
        return [asset.model_dump() for asset in summary.cover_assets]

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        try:
            record = service.cancel(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "record": record.to_dict(),
            "summary": summary_service.build_summary(record).model_dump(),
        }

    @app.post("/api/tasks/{task_id}/retry")
    def retry_task(task_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        source_record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        _ensure_session_llm_config(auth_manager, session, dry_run=source_record.request.dry_run)
        try:
            record = service.retry(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "source_task_id": task_id,
            "record": record.to_dict(),
            "summary": summary_service.build_summary(record).model_dump(),
        }

    @app.post("/api/tasks/{task_id}/assets")
    async def upload_task_asset(
        task_id: str,
        request: Request,
        file: UploadFile = File(...),
        asset_type: Literal["board_photo", "waveform_capture", "log_snapshot", "artifact_preview"] = Form(...),
        caption: str = Form(""),
        is_cover: bool = Form(False),
    ) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)

        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        asset = asset_store.add_asset(
            task_id=task_id,
            asset_type=asset_type,
            file_name=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            caption=caption,
            is_cover=is_cover,
        )
        summary = summary_service.build_summary(record)
        uploaded_asset = next((item for item in summary.cover_assets if item.asset_id == asset.asset_id), None)
        return {
            "asset": uploaded_asset.model_dump() if uploaded_asset else asset.to_dict(),
            "summary": summary.model_dump(),
        }

    @app.post("/api/tasks/{task_id}/assets/{asset_id}/cover")
    def set_cover(task_id: str, asset_id: str, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        record = _get_task_or_404(service, task_id, auth_manager=auth_manager, session=session)
        try:
            asset_store.set_cover(task_id, asset_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        summary = summary_service.build_summary(record)
        return {"summary": summary.model_dump()}

    @app.post("/api/tasks")
    def submit_task(payload: TaskSubmissionPayload, request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        _ensure_session_llm_config(auth_manager, session, dry_run=payload.dry_run)
        request_metadata = dict(payload.metadata)
        if session is not None:
            request_metadata[AUTH_SUBJECT_METADATA_KEY] = session.subject_id
        request = _build_request_from_payload(payload, service.repo_root, metadata=request_metadata)
        if payload.execution == "sync":
            execution = service.run_sync(request)
            summary = summary_service.build_summary(execution.record)
            return {
                "record": execution.record.to_dict(),
                "summary": summary.model_dump(),
                "manifest": execution.manifest,
            }

        record = service.enqueue(request)
        summary = summary_service.build_summary(record)
        return {
            "record": record.to_dict(),
            "summary": summary.model_dump(),
        }

    @app.post("/api/tasks/run-next")
    def run_next(request: Request) -> dict[str, Any]:
        session = _require_session_if_enabled(auth_manager, request)
        visible_records = _list_visible_records(service, auth_manager, session)
        if any(record.status == "pending" and not record.request.dry_run for record in visible_records):
            _ensure_session_llm_config(auth_manager, session, dry_run=False)
        predicate = None if session is None else lambda record: auth_manager.owns_subject(record.request.metadata, session)
        execution = service.run_next_queued(predicate=predicate)
        if execution is None:
            return {"status": "empty"}
        summary = summary_service.build_summary(execution.record)
        return {
            "status": "executed",
            "record": execution.record.to_dict(),
            "summary": summary.model_dump(),
            "manifest": execution.manifest,
        }

    return app


def _build_request_from_payload(
    payload: TaskSubmissionPayload,
    repo_root: Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> AgentTaskRequest:
    output_dir = Path(payload.output_dir) if payload.output_dir else _default_output_dir(repo_root, payload.task_kind)
    task_file = Path(payload.task_file) if payload.task_file else None
    title = payload.title or (task_file.stem if task_file else f"{payload.task_kind}-{output_dir.name}")

    requirement_text = payload.requirement_text
    if task_file is not None and not requirement_text:
        requirement_text = task_file.read_text(encoding="utf-8")

    return AgentTaskRequest(
        title=title,
        requirement_text=requirement_text,
        output_dir=output_dir,
        task_file=task_file,
        mode=payload.mode,
        dry_run=payload.dry_run,
        task_kind=payload.task_kind,
        origin="api",
        metadata=metadata if metadata is not None else payload.metadata,
    )


def _default_output_dir(repo_root: Path, task_kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return repo_root / "runs" / f"api_{task_kind}_{stamp}_{uuid4().hex[:6]}"


def _build_dashboard_snapshot(summary_service: TaskSummaryService, records: list[AgentTaskRecord]) -> dict[str, Any]:
    summaries = summary_service.build_many(records)
    gallery = summary_service.build_gallery(records)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tasks": [summary.model_dump() for summary in summaries],
        "gallery": [item.model_dump() for item in gallery],
    }


def _build_dashboard_events(previous: dict[str, Any], current: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    previous_tasks = {item["status"]["task_id"]: item for item in previous.get("tasks", [])}
    current_tasks = {item["status"]["task_id"]: item for item in current.get("tasks", [])}

    for task_id, task_payload in current_tasks.items():
        if _json_signature(task_payload) != _json_signature(previous_tasks.get(task_id)):
            events.append(("task-upsert", task_payload))

    for task_id in previous_tasks.keys() - current_tasks.keys():
        events.append(("task-remove", {"task_id": task_id}))

    current_gallery = {"gallery": current.get("gallery", [])}
    previous_gallery = {"gallery": previous.get("gallery", [])}
    if _json_signature(current_gallery) != _json_signature(previous_gallery):
        events.append(("gallery-updated", current_gallery))

    return events


def _format_sse_event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _json_signature(payload: Any) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)


def _get_task_or_404(
    service: AgentTaskService,
    task_id: str,
    *,
    auth_manager: AuthManager | None = None,
    session: AuthSession | None = None,
) -> AgentTaskRecord:
    record = service.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if auth_manager is not None and auth_manager.enabled and not auth_manager.owns_subject(record.request.metadata, session):
        raise HTTPException(status_code=404, detail="Task not found")
    return record


def _require_session_if_enabled(auth_manager: AuthManager, request: Request) -> AuthSession | None:
    if not auth_manager.enabled:
        return None
    return auth_manager.require_session(request)


def _list_visible_records(
    service: AgentTaskService,
    auth_manager: AuthManager,
    session: AuthSession | None,
) -> list[AgentTaskRecord]:
    records = service.list_queue()
    if not auth_manager.enabled:
        return records
    return [record for record in records if auth_manager.owns_subject(record.request.metadata, session)]


def _ensure_session_llm_config(auth_manager: AuthManager, session: AuthSession | None, *, dry_run: bool) -> None:
    if dry_run or not auth_manager.enabled:
        return
    if session is None:
        raise HTTPException(status_code=401, detail="Login required.")
    if auth_manager.get_llm_config(session) is not None:
        return
    server_provider_ready = bool(os.getenv("DIGITAL_IC_AGENT_API_KEY", "").strip())
    if not auth_manager.allow_shared_llm or not server_provider_ready:
        raise HTTPException(
            status_code=409,
            detail="Please save your personal API configuration before submitting or running tasks.",
        )


def _resolve_preview_or_404(
    summary_service: TaskSummaryService,
    record,
    category: Literal["artifact", "log"],
    file_name: str,
) -> Path:
    try:
        return summary_service.resolve_preview_path(record, category, file_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"{category} file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


app = build_app()


def run() -> None:
    import uvicorn

    uvicorn.run("digital_ic_agent.api:app", host="127.0.0.1", port=8000, reload=False)
