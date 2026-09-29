from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .config import AppConfig
from .artifact_layout import ensure_delivery_directories, structured_path
from .feedback_loop import FeedbackLoop
from .llm import warm_llm_capability_probe_from_env
from .prechecks import (
    build_interface_contract_check_result,
    load_interface_contract,
    run_prechecked_eda,
)
from .skill_governance import build_governance_artifacts
from .task_models import AgentTaskExecution, AgentTaskRecord, AgentTaskRequest
from .task_queue import FileTaskQueue
from .task_kinds import build_effective_request_text, get_task_kind_definition
from .template_library import RenderedTemplate
from .workflow import run_workflow


class TaskCancellationRequested(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(f"Cancellation requested at stage: {stage}")
        self.stage = stage


class ArtifactWriter:
    def write_partial(self, *, record: AgentTaskRecord, state: dict[str, Any], task_file: Path) -> None:
        output_dir = record.request.output_dir
        ensure_delivery_directories(output_dir)
        task_input_path = output_dir / structured_path("task_input.md")
        if not task_input_path.exists() and task_file.exists():
            task_input_path.write_text(task_file.read_text(encoding="utf-8"), encoding="utf-8")
        self._write_state_files(output_dir=output_dir, state=state)

    def write(
        self,
        *,
        record: AgentTaskRecord,
        config: AppConfig,
        state: dict,
        task_file: Path,
    ) -> dict:
        output_dir = record.request.output_dir
        ensure_delivery_directories(output_dir)

        task_input_path = output_dir / structured_path("task_input.md")
        if not task_input_path.exists() and task_file.exists():
            task_input_path.write_text(task_file.read_text(encoding="utf-8"), encoding="utf-8")
        self._write_state_files(output_dir=output_dir, state=state)
        (output_dir / structured_path("delivery_report.md")).write_text(
            self._build_delivery_report(record=record, config=config, state=state),
            encoding="utf-8",
        )

        model_label = str(state.get("model_label") or config.model)
        manifest = {
            "task_id": record.task_id,
            "task_kind": record.request.task_kind,
            "title": record.request.title,
            "origin": record.request.origin,
            "task_file": str(task_file),
            "mode": config.mode,
            "dry_run": config.dry_run,
            "model": model_label,
            "repair_attempts": state.get("repair_attempts", 0),
            "output_dir": str(output_dir),
            "metadata": record.request.metadata,
            "primary_deliverable": structured_path("delivery_report.md"),
            "execution_path": state.get("execution_path", "llm_workflow"),
        }
        self._write_json(output_dir / structured_path("run_manifest.json"), manifest)
        return manifest

    def _write_state_files(self, *, output_dir: Path, state: dict[str, Any]) -> None:
        if "llm_trace" in state:
            self._write_json(output_dir / structured_path("llm_trace.json"), state["llm_trace"])
        if "requirement_analysis" in state:
            self._write_json(output_dir / structured_path("requirement_analysis.json"), state["requirement_analysis"])
        if "architecture_design" in state:
            self._write_json(output_dir / structured_path("architecture_design.json"), state["architecture_design"])
        if "specification" in state:
            (output_dir / structured_path("specification.md")).write_text(state["specification"], encoding="utf-8")
        if "rtl_code" in state:
            (output_dir / structured_path("rtl_code.v")).write_text(state["rtl_code"], encoding="utf-8")
        if "testbench_code" in state:
            (output_dir / structured_path("testbench.v")).write_text(state["testbench_code"], encoding="utf-8")
        if "eda_result" in state:
            self._write_json(output_dir / structured_path("eda_result.json"), state["eda_result"])
            (output_dir / structured_path("simulation.log")).write_text(
                state["eda_result"].get("simulation_log", ""),
                encoding="utf-8",
            )
            (output_dir / structured_path("yosys.log")).write_text(
                state["eda_result"].get("yosys_log", ""),
                encoding="utf-8",
            )
        if "review" in state:
            self._write_json(output_dir / structured_path("review.json"), state["review"])
        if "repair_response" in state:
            (output_dir / structured_path("repair_response.md")).write_text(state["repair_response"], encoding="utf-8")
        if "repair_history" in state:
            self._write_json(output_dir / structured_path("repair_history.json"), {"history": state["repair_history"]})
        if "feedback_report" in state:
            self._write_json(output_dir / structured_path("feedback_report.json"), state["feedback_report"])
        if "feedback_memory_snapshot" in state:
            self._write_json(output_dir / structured_path("feedback_memory_snapshot.json"), state["feedback_memory_snapshot"])
        if "skill_card" in state:
            self._write_json(output_dir / structured_path("skill_card.json"), state["skill_card"])
        if "security_report" in state:
            self._write_json(output_dir / structured_path("security_report.json"), state["security_report"])

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _build_delivery_report(*, record: AgentTaskRecord, config: AppConfig, state: dict[str, Any]) -> str:
        eda = state.get("eda_result") if isinstance(state.get("eda_result"), dict) else {}
        review = state.get("review") if isinstance(state.get("review"), dict) else {}
        architecture = state.get("architecture_design") if isinstance(state.get("architecture_design"), dict) else {}
        repairs = list(state.get("repair_history") or [])
        passed = bool(eda.get("overall_pass")) if eda else None
        verdict = "通过" if passed is True else "未通过" if passed is False else "未执行 EDA"

        def bullets(values: Any, empty: str = "无") -> str:
            if not isinstance(values, list) or not values:
                return f"- {empty}"
            return "\n".join(f"- {value}" for value in values)

        repair_lines = [
            f"- 第 {item.get('attempt', index)} 次：{item.get('summary') or item.get('label') or '已执行修复'}"
            for index, item in enumerate(repairs, start=1)
            if isinstance(item, dict)
        ]
        requirements = record.request.requirement_text.strip() or "见 task_input.md"
        model_label = str(state.get("model_label") or config.model)
        execution_path_labels = {
            "llm_workflow": "大模型生成与 EDA 闭环",
            "parameterized_template_library": "参数化模板库零 Token 实例化",
        }
        execution_path = str(state.get("execution_path", "llm_workflow"))
        return f"""# 数字 IC Agent 最终交付说明书

## 1. 任务概览

- 任务 ID：`{record.task_id}`
- 标题：{record.request.title}
- 任务类型：`{record.request.task_kind}`
- 目标模式：`{config.mode}`
- 生成引擎：`{model_label}`
- 执行路径：`{execution_path_labels.get(execution_path, execution_path)}`
- 最终质量门：**{verdict}**

## 2. 用户原始需求

{requirements}

## 3. Agent 自动设计结论

### 架构输出

{bullets(architecture.get('outputs'), '详见 architecture_design.json 与 specification.md')}

### 约束与假设

{bullets(architecture.get('constraints'), '详见 specification.md')}

## 4. 生成产物

- `doc/specification.md`：由原始赛题自动澄清得到的可实现规格与接口契约。
- `rtl/rtl_code.v`：可综合 Verilog RTL。
- `tb/testbench.v`：确定性、自检查 Testbench。
- `doc/eda_result.json`、`logs/simulation.log`、`logs/yosys.log`：仿真与综合证据。
- `doc/review.json`：一致性与风险审查。
- `doc/skill_card.json`、`doc/security_report.json`：Skill 治理与安全边界证据。
- `meta/run_manifest.json`：可复现运行清单。

## 5. 自动验证结果

- 仿真：{'通过' if eda.get('simulation_passed') else '未通过或未执行'}
- 综合：{'通过' if eda.get('synthesis_passed') else '未通过或未执行'}
- 总体质量门：{verdict}
- 修复轮数：{state.get('repair_attempts', 0)}

## 6. 反馈修复闭环

{chr(10).join(repair_lines) if repair_lines else '- 首轮输出通过，或本任务未触发自动修复。'}

## 7. Review 摘要

{review.get('task_summary') or '详见 review.json。'}

### 已识别风险

{bullets(review.get('technical_risks'), '未记录额外风险')}

## 8. 复现方式

在工程根目录激活 Python 环境并确认 Icarus Verilog、vvp 与 Yosys 可用，然后通过 GUI 提交同一需求；`doc/task_input.md` 与 `meta/run_manifest.json` 保存输入和运行配置。RTL 可用 `rtl/rtl_code.v`，验证环境可用 `tb/testbench.v` 独立复核。

## 9. 交付结论

本交付仅在仿真与综合均通过时视为闭环成功。若质量门为“未通过”，请先查看 `eda_result.json` 和日志，不应将仅能生成文本或仅通过语法检查的结果宣称为完成。
"""


class AgentTaskService:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        queue: FileTaskQueue | None = None,
        artifact_writer: ArtifactWriter | None = None,
        llm_config_resolver: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    ) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self.queue = queue or FileTaskQueue(self.repo_root / ".agent_queue")
        self.artifact_writer = artifact_writer or ArtifactWriter()
        self.llm_capability_probe = warm_llm_capability_probe_from_env()
        self.llm_config_resolver = llm_config_resolver
        self.feedback_loop = FeedbackLoop(self.repo_root)

    def run_sync(self, request: AgentTaskRequest) -> AgentTaskExecution:
        record = AgentTaskRecord.create(request)
        self.queue.save(record)
        return self._execute(record, persist_queue_state=True)

    def enqueue(self, request: AgentTaskRequest) -> AgentTaskRecord:
        return self.queue.submit(request)

    def list_queue(self) -> list[AgentTaskRecord]:
        return self.queue.list_tasks()

    def get_task(self, task_id: str) -> AgentTaskRecord | None:
        return self.queue.get(task_id)

    def run_template(
        self,
        rendered: RenderedTemplate,
        *,
        title: str | None = None,
        output_dir: Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTaskExecution:
        """Instantiate a verified template without spending model tokens."""
        target_dir = output_dir or (
            self.repo_root / "runs" / "template_library" / f"{rendered.template_id}_{uuid4().hex[:10]}"
        )
        request = AgentTaskRequest(
            title=title or rendered.title,
            requirement_text=rendered.requirement_text,
            output_dir=target_dir,
            mode="fpga",
            dry_run=True,
            task_kind="rtl_module_generation",
            origin="template_library",
            metadata={
                **(metadata or {}),
                "template_id": rendered.template_id,
                "template_parameters": rendered.parameters,
                "token_usage": 0,
            },
        )
        pending = AgentTaskRecord.create(request)
        running = pending.mark_running()
        self.queue.save(running)
        ensure_delivery_directories(target_dir)
        task_file = target_dir / structured_path("task_input.md")
        task_file.write_text(rendered.requirement_text, encoding="utf-8")
        try:
            eda_result = run_prechecked_eda(
                run_dir=target_dir,
                repo_root=self.repo_root,
                rtl_code=rendered.rtl_code,
                testbench_code=rendered.testbench_code,
                interface_contract="",
            )
            state: dict[str, Any] = {
                "requirement_analysis": {
                    "来源": "参数化模板库",
                    "模板": rendered.template_id,
                    "参数": rendered.parameters,
                },
                "architecture_design": {
                    "outputs": ["参数化 RTL", "自检查测试平台", "EDA 验证报告"],
                    "constraints": ["模板实例化后必须重新通过仿真与综合质量门"],
                },
                "specification": rendered.specification,
                "rtl_code": rendered.rtl_code,
                "testbench_code": rendered.testbench_code,
                "eda_result": eda_result,
                "review": {
                    "task_summary": "从参数化模板库零 Token 实例化，并完成独立 EDA 复核。",
                    "inputs": [rendered.requirement_text],
                    "outputs": ["RTL", "测试平台", "验证证据"],
                    "constraints": ["参数范围由模板清单约束"],
                    "performance_targets": [],
                    "technical_risks": list(eda_result.get("precheck_issues") or []),
                    "questions_to_clarify": [],
                },
                "repair_attempts": 0,
                "repair_history": [],
                "execution_path": "parameterized_template_library",
                "model_label": "参数化模板库（未调用大模型）",
                "llm_trace": {
                    "status": "未调用模型",
                    "reason": "命中已验证参数化模板",
                    "token_usage": 0,
                },
            }
            state.update(
                build_governance_artifacts(
                    repo_root=self.repo_root,
                    task_kind=request.task_kind,
                    metadata=request.metadata,
                )
            )
            state.update(self.feedback_loop.capture(record=running, state=state))
            config = AppConfig.from_env(mode="fpga", dry_run=True, repo_root=self.repo_root)
            manifest = self.artifact_writer.write(
                record=running,
                config=config,
                state=state,
                task_file=task_file,
            )
            if eda_result.get("overall_pass"):
                completed = running.mark_succeeded(model="参数化模板库", repair_attempts=0)
            else:
                completed = running.mark_failed(error="模板实例化后的 EDA 质量门未通过。", model="参数化模板库")
            self.queue.save(completed)
            return AgentTaskExecution(record=completed, workflow_state=state, manifest=manifest)
        except Exception as exc:
            failed = running.mark_failed(error=str(exc), model="参数化模板库")
            self.queue.save(failed)
            raise

    def cancel(self, task_id: str) -> AgentTaskRecord:
        record = self.queue.get(task_id)
        if record is None:
            raise KeyError(task_id)
        if record.status == "pending":
            canceled_record = record.mark_canceled(reason="Canceled before execution.", stage="queue")
            self.queue.save(canceled_record)
            return canceled_record
        if record.status == "running":
            requested_record = record.request_cancel()
            self.queue.save(requested_record)
            return requested_record
        raise ValueError("Only pending or running tasks can be canceled.")

    def retry(self, task_id: str) -> AgentTaskRecord:
        record = self.queue.get(task_id)
        if record is None:
            raise KeyError(task_id)
        if record.status in {"pending", "running"}:
            raise ValueError("Only finished, failed, or canceled tasks can be retried.")

        return self.queue.submit(self._build_retry_request(record))

    def run_next_queued(self, predicate: Callable[[AgentTaskRecord], bool] | None = None) -> AgentTaskExecution | None:
        record = self.queue.claim_next(predicate)
        if record is None:
            return None
        return self._execute(record, persist_queue_state=True)

    def _build_retry_request(self, record: AgentTaskRecord) -> AgentTaskRequest:
        metadata = dict(record.request.metadata)
        previous_retry_count = metadata.get("retry_count", 0)
        try:
            retry_count = int(previous_retry_count) + 1
        except (TypeError, ValueError):
            retry_count = 1

        metadata["retry_of"] = record.task_id
        metadata["retry_count"] = retry_count

        return AgentTaskRequest(
            title=record.request.title,
            requirement_text=record.request.requirement_text,
            output_dir=self._make_retry_output_dir(record.request.output_dir, retry_count),
            task_file=record.request.task_file,
            mode=record.request.mode,
            dry_run=record.request.dry_run,
            task_kind=record.request.task_kind,
            origin=record.request.origin,
            metadata=metadata,
        )

    @staticmethod
    def _make_retry_output_dir(output_dir: Path, retry_count: int) -> Path:
        candidate = output_dir.parent / f"{output_dir.name}_retry{retry_count}"
        suffix = retry_count
        while candidate.exists():
            suffix += 1
            candidate = output_dir.parent / f"{output_dir.name}_retry{suffix}"
        return candidate

    def _execute(self, record: AgentTaskRecord, *, persist_queue_state: bool) -> AgentTaskExecution:
        request = record.request
        definition = get_task_kind_definition(request.task_kind)
        config = self._build_runtime_config(request)
        task_file = self._materialize_task_file(request)
        running_record = record if record.status == "running" else record.mark_running()
        checkpoint_state: dict[str, Any] = {}

        if persist_queue_state:
            self.queue.save(running_record)

        cancellation_check = self._make_cancellation_check(running_record.task_id)
        stage_checkpoint = self._make_stage_checkpoint(
            record=running_record,
            task_file=task_file,
            checkpoint_state=checkpoint_state,
            cancellation_check=cancellation_check,
        )
        llm_trace_update = self._make_llm_trace_update(
            record=running_record,
            task_file=task_file,
            checkpoint_state=checkpoint_state,
        )

        try:
            if definition.execution_strategy == "workflow":
                state = self._execute_workflow_task(
                    request,
                    config,
                    task_file,
                    cancellation_check=cancellation_check,
                    stage_checkpoint=stage_checkpoint,
                    llm_trace_update=llm_trace_update,
                )
            elif definition.execution_strategy == "eda_triage":
                state = self._execute_eda_triage_task(
                    request,
                    config,
                    task_file,
                    cancellation_check=cancellation_check,
                    stage_checkpoint=stage_checkpoint,
                )
            elif definition.execution_strategy == "interface_contract_check":
                state = self._execute_interface_contract_check_task(
                    request,
                    config,
                    task_file,
                    cancellation_check=cancellation_check,
                    stage_checkpoint=stage_checkpoint,
                )
            else:
                raise ValueError(f"Unsupported execution strategy: {definition.execution_strategy}")
            if checkpoint_state.get("llm_trace") is not None and state.get("llm_trace") is None:
                state["llm_trace"] = checkpoint_state["llm_trace"]
            state.update(
                build_governance_artifacts(
                    repo_root=self.repo_root,
                    task_kind=request.task_kind,
                    metadata=request.metadata,
                )
            )
            state.update(self.feedback_loop.capture(record=running_record, state=state))
            manifest = self.artifact_writer.write(
                record=running_record,
                config=config,
                state=state,
                task_file=task_file,
            )
            quality_error = self._quality_gate_error(state)
            if quality_error:
                completed_record = running_record.mark_failed(error=quality_error, model=config.model)
            else:
                completed_record = running_record.mark_succeeded(
                    model=config.model,
                    repair_attempts=state.get("repair_attempts", 0),
                )
            if persist_queue_state:
                self.queue.save(completed_record)
            return AgentTaskExecution(
                record=completed_record,
                workflow_state=state,
                manifest=manifest,
            )
        except TaskCancellationRequested as exc:
            latest_record = self.queue.get(running_record.task_id) or running_record
            canceled_record = latest_record.mark_canceled(stage=exc.stage)
            if persist_queue_state:
                self.queue.save(canceled_record)
            return AgentTaskExecution(
                record=canceled_record,
                workflow_state=dict(checkpoint_state),
                manifest={},
            )
        except Exception as exc:
            failed_record = running_record.mark_failed(error=str(exc), model=config.model)
            failure_state = dict(checkpoint_state)
            failure_state.update(self.feedback_loop.capture(record=failed_record, state=failure_state, error=str(exc)))
            self.artifact_writer.write_partial(record=failed_record, state=failure_state, task_file=task_file)
            if persist_queue_state:
                self.queue.save(failed_record)
            raise

    @staticmethod
    def _quality_gate_error(state: dict[str, Any]) -> str | None:
        eda_result = state.get("eda_result")
        if not isinstance(eda_result, dict):
            # Real execution strategies emit EDA results. A missing result is
            # left neutral for injected workflows used by API integrations.
            return None
        if bool(eda_result.get("overall_pass")):
            return None

        failed_checks: list[str] = []
        if not eda_result.get("simulation_passed"):
            failed_checks.append("simulation")
        if not eda_result.get("synthesis_passed"):
            failed_checks.append("synthesis")
        if eda_result.get("interface_contract_failed"):
            failed_checks.append("interface contract")
        if eda_result.get("testbench_precheck_failed"):
            failed_checks.append("testbench precheck")
        if eda_result.get("missing_tools"):
            failed_checks.append("EDA tool availability")
        detail = ", ".join(dict.fromkeys(failed_checks)) or "EDA overall result"
        return f"Quality gate failed: {detail} did not pass. Inspect eda_result.json and logs."

    def _build_runtime_config(self, request: AgentTaskRequest) -> AppConfig:
        overrides = self.llm_config_resolver(request.metadata) if self.llm_config_resolver is not None else None
        return AppConfig.from_env(
            mode=request.mode,
            dry_run=request.dry_run,
            repo_root=self.repo_root,
            overrides=overrides,
        )

    @staticmethod
    def _materialize_task_file(request: AgentTaskRequest) -> Path:
        if request.task_file is not None:
            return request.task_file

        ensure_delivery_directories(request.output_dir)
        generated_task_file = request.output_dir / structured_path("task_input.md")
        generated_task_file.write_text(request.requirement_text, encoding="utf-8")
        return generated_task_file

    @staticmethod
    def _execute_workflow_task(
        request: AgentTaskRequest,
        config: AppConfig,
        task_file: Path,
        *,
        cancellation_check: Callable[[str], None],
        stage_checkpoint: Callable[[str, dict[str, Any] | None], None],
        llm_trace_update: Callable[[dict[str, Any]], None],
    ) -> dict:
        return run_workflow(
            request=build_effective_request_text(request.task_kind, request.requirement_text),
            task_file=task_file,
            config=config,
            run_dir=request.output_dir,
            task_kind=request.task_kind,
            cancellation_check=cancellation_check,
            stage_checkpoint=stage_checkpoint,
            llm_trace_update=llm_trace_update,
        )

    def _execute_eda_triage_task(
        self,
        request: AgentTaskRequest,
        config: AppConfig,
        task_file: Path,
        *,
        cancellation_check: Callable[[str], None],
        stage_checkpoint: Callable[[str, dict[str, Any] | None], None],
    ) -> dict:
        stage_checkpoint("eda_triage:start", None)
        rtl_code = self._resolve_artifact_text(request, text_key="rtl_code", path_key="rtl_path")
        testbench_code = self._resolve_artifact_text(request, text_key="testbench_code", path_key="testbench_path")
        interface_contract = self._resolve_interface_contract(request, task_file)
        stage_checkpoint(
            "eda_triage:inputs",
            {
                "requirement_analysis": {},
                "architecture_design": {},
                "specification": request.requirement_text or "EDA triage task",
                "rtl_code": rtl_code,
                "testbench_code": testbench_code,
                "repair_attempts": 0,
                "repair_history": [],
            },
        )
        eda_result = run_prechecked_eda(
            run_dir=request.output_dir,
            repo_root=config.repo_root,
            rtl_code=rtl_code,
            testbench_code=testbench_code,
            interface_contract=interface_contract,
            cancellation_check=cancellation_check,
        )
        state = {
            "requirement_analysis": {},
            "architecture_design": {},
            "specification": request.requirement_text or "EDA triage task",
            "rtl_code": rtl_code,
            "testbench_code": testbench_code,
            "eda_result": eda_result,
            "review": self._build_direct_task_review(
                request_title=request.title,
                review_label="EDA triage",
                issues=eda_result.get("precheck_issues") or [],
            ),
            "repair_attempts": 0,
            "repair_history": [],
        }
        stage_checkpoint("eda_triage:complete", state)
        return state

    def _execute_interface_contract_check_task(
        self,
        request: AgentTaskRequest,
        config: AppConfig,
        task_file: Path,
        *,
        cancellation_check: Callable[[str], None],
        stage_checkpoint: Callable[[str, dict[str, Any] | None], None],
    ) -> dict:
        stage_checkpoint("interface_contract_check:start", None)
        rtl_code = self._resolve_artifact_text(request, text_key="rtl_code", path_key="rtl_path")
        interface_contract = self._resolve_interface_contract(request, task_file)
        if not interface_contract:
            raise ValueError(
                "interface_contract_check requires metadata.interface_contract, metadata.contract_path, or a task file with a sibling .interface.v/.contract.v file."
            )
        eda_result = build_interface_contract_check_result(
            run_dir=request.output_dir,
            rtl_code=rtl_code,
            interface_contract=interface_contract,
        )
        cancellation_check("interface_contract_check:post-build")
        state = {
            "requirement_analysis": {},
            "architecture_design": {},
            "specification": request.requirement_text or "Interface contract check task",
            "rtl_code": rtl_code,
            "testbench_code": "",
            "eda_result": eda_result,
            "review": self._build_direct_task_review(
                request_title=request.title,
                review_label="Interface contract check",
                issues=eda_result.get("precheck_issues") or [],
            ),
            "repair_attempts": 0,
            "repair_history": [],
        }
        stage_checkpoint("interface_contract_check:complete", state)
        return state

    def _make_cancellation_check(self, task_id: str) -> Callable[[str], None]:
        def check(stage: str) -> None:
            record = self.queue.get(task_id)
            if record is not None and record.cancel_requested:
                raise TaskCancellationRequested(stage)

        return check

    def _make_stage_checkpoint(
        self,
        *,
        record: AgentTaskRecord,
        task_file: Path,
        checkpoint_state: dict[str, Any],
        cancellation_check: Callable[[str], None],
    ) -> Callable[[str, dict[str, Any] | None], None]:
        def checkpoint(stage: str, updates: dict[str, Any] | None) -> None:
            cancellation_check(stage)
            if updates:
                checkpoint_state.update(updates)
                self.artifact_writer.write_partial(record=record, state=checkpoint_state, task_file=task_file)
            cancellation_check(stage)

        return checkpoint

    def _make_llm_trace_update(
        self,
        *,
        record: AgentTaskRecord,
        task_file: Path,
        checkpoint_state: dict[str, Any],
    ) -> Callable[[dict[str, Any]], None]:
        def update(trace: dict[str, Any]) -> None:
            checkpoint_state["llm_trace"] = dict(trace)
            self.artifact_writer.write_partial(record=record, state=checkpoint_state, task_file=task_file)

        return update

    @staticmethod
    def _resolve_artifact_text(request: AgentTaskRequest, *, text_key: str, path_key: str) -> str:
        metadata = request.metadata
        inline_text = metadata.get(text_key)
        if isinstance(inline_text, str) and inline_text.strip():
            return inline_text

        artifact_path = metadata.get(path_key)
        if isinstance(artifact_path, str) and artifact_path.strip():
            return Path(artifact_path).read_text(encoding="utf-8")

        raise ValueError(
            f"Task kind '{request.task_kind}' requires metadata.{text_key} or metadata.{path_key}."
        )

    @staticmethod
    def _resolve_interface_contract(request: AgentTaskRequest, task_file: Path) -> str:
        metadata = request.metadata
        inline_contract = metadata.get("interface_contract")
        if isinstance(inline_contract, str) and inline_contract.strip():
            return inline_contract

        contract_path = metadata.get("contract_path")
        if isinstance(contract_path, str) and contract_path.strip():
            return Path(contract_path).read_text(encoding="utf-8")

        return load_interface_contract(task_file)

    @staticmethod
    def _build_direct_task_review(*, request_title: str, review_label: str, issues: list[str]) -> dict:
        return {
            "task_summary": f"{review_label}: {request_title}",
            "inputs": [request_title],
            "outputs": [review_label],
            "constraints": [],
            "performance_targets": [],
            "technical_risks": issues,
            "questions_to_clarify": [],
        }
