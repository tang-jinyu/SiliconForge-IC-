from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .artifact_layout import ensure_delivery_directories, resolve_delivery_path, structured_path
from .prechecks import run_prechecked_eda
from .task_models import AgentTaskRecord, AgentTaskRequest
from .task_service import AgentTaskService


@dataclass(frozen=True)
class BenchmarkExpectation:
    overall_pass: bool | None = None
    simulation_passed: bool | None = None
    synthesis_passed: bool | None = None
    max_repair_attempts: int | None = None
    required_artifacts: tuple[str, ...] = ()
    forbidden_precheck_substrings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    title: str
    task_kind: str
    task_file: Path
    mode: str
    dry_run: bool
    metadata: dict[str, Any]
    expectation: BenchmarkExpectation
    oracle_testbench: Path | None = None


def load_benchmark_case(case_dir: Path) -> BenchmarkCase:
    payload = json.loads((case_dir / "benchmark_case.json").read_text(encoding="utf-8"))
    expectation_payload = dict(payload.get("expected") or {})
    task_file_name = str(payload.get("task_file") or "task.md")
    metadata = dict(payload.get("metadata") or {})
    oracle_name = payload.get("oracle_testbench")
    oracle_testbench = (case_dir / str(oracle_name)).resolve() if oracle_name else None
    for key in ("rtl_path", "testbench_path", "contract_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            candidate = Path(value)
            if not candidate.is_absolute():
                metadata[key] = str((case_dir / candidate).resolve())
    return BenchmarkCase(
        case_id=str(payload.get("case_id") or case_dir.name),
        title=str(payload.get("title") or case_dir.name),
        task_kind=str(payload.get("task_kind") or "rtl_module_generation"),
        task_file=case_dir / task_file_name,
        mode=str(payload.get("mode") or "fpga"),
        dry_run=bool(payload.get("dry_run", False)),
        metadata=metadata,
        expectation=BenchmarkExpectation(
            overall_pass=_optional_bool(expectation_payload.get("overall_pass")),
            simulation_passed=_optional_bool(expectation_payload.get("simulation_passed")),
            synthesis_passed=_optional_bool(expectation_payload.get("synthesis_passed")),
            max_repair_attempts=_optional_int(expectation_payload.get("max_repair_attempts")),
            required_artifacts=tuple(expectation_payload.get("required_artifacts") or ()),
            forbidden_precheck_substrings=tuple(expectation_payload.get("forbidden_precheck_substrings") or ()),
        ),
        oracle_testbench=oracle_testbench,
    )


def list_benchmark_cases(suite_dir: Path) -> list[BenchmarkCase]:
    return [
        load_benchmark_case(case_json.parent)
        for case_json in sorted(suite_dir.rglob("benchmark_case.json"))
    ]


def score_benchmark_case(
    case: BenchmarkCase,
    *,
    record: AgentTaskRecord,
    state: dict[str, Any],
) -> dict[str, Any]:
    self_eda_result = dict(state.get("eda_result") or {})
    blind_eda_result = dict(state.get("blind_eda_result") or {})
    eda_result = blind_eda_result or self_eda_result
    precheck_issues = list(eda_result.get("precheck_issues") or [])
    output_dir = record.request.output_dir

    checks: list[dict[str, Any]] = [
        {
            "name": "task_succeeded",
            "weight": 1,
            "passed": record.status == "succeeded",
            "detail": f"task status={record.status}",
        }
    ]

    if case.expectation.overall_pass is not None:
        actual = bool(eda_result.get("overall_pass"))
        checks.append(
            {
                "name": "overall_pass",
                "weight": 3,
                "passed": actual == case.expectation.overall_pass,
                "detail": f"expected overall_pass={case.expectation.overall_pass}, actual={actual}",
            }
        )

    if case.expectation.simulation_passed is not None:
        actual = bool(eda_result.get("simulation_passed"))
        checks.append(
            {
                "name": "simulation_passed",
                "weight": 2,
                "passed": actual == case.expectation.simulation_passed,
                "detail": f"expected simulation_passed={case.expectation.simulation_passed}, actual={actual}",
            }
        )

    if case.expectation.synthesis_passed is not None:
        actual = bool(eda_result.get("synthesis_passed"))
        checks.append(
            {
                "name": "synthesis_passed",
                "weight": 2,
                "passed": actual == case.expectation.synthesis_passed,
                "detail": f"expected synthesis_passed={case.expectation.synthesis_passed}, actual={actual}",
            }
        )

    if case.expectation.max_repair_attempts is not None:
        actual = int(state.get("repair_attempts", 0))
        checks.append(
            {
                "name": "repair_budget",
                "weight": 1,
                "passed": actual <= case.expectation.max_repair_attempts,
                "detail": f"expected repair_attempts<={case.expectation.max_repair_attempts}, actual={actual}",
            }
        )

    if case.expectation.required_artifacts:
        missing_artifacts = [
            file_name
            for file_name in case.expectation.required_artifacts
            if not resolve_delivery_path(output_dir, file_name).exists()
        ]
        checks.append(
            {
                "name": "required_artifacts",
                "weight": 1,
                "passed": not missing_artifacts,
                "detail": "all required artifacts present"
                if not missing_artifacts
                else "missing artifacts: " + ", ".join(missing_artifacts),
            }
        )

    if case.expectation.forbidden_precheck_substrings:
        offenders = [
            snippet
            for snippet in case.expectation.forbidden_precheck_substrings
            if any(snippet in issue for issue in precheck_issues)
        ]
        checks.append(
            {
                "name": "forbidden_precheck_substrings",
                "weight": 1,
                "passed": not offenders,
                "detail": "no forbidden precheck substrings found"
                if not offenders
                else "forbidden precheck matches: " + ", ".join(offenders),
            }
        )

    total_weight = sum(item["weight"] for item in checks)
    passed_weight = sum(item["weight"] for item in checks if item["passed"])
    score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0

    return {
        "case_id": case.case_id,
        "title": case.title,
        "task_id": record.task_id,
        "task_status": record.status,
        "score": score,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "repair_attempts": int(state.get("repair_attempts", 0)),
        "eda_summary": {
            "overall_pass": eda_result.get("overall_pass"),
            "simulation_passed": eda_result.get("simulation_passed"),
            "synthesis_passed": eda_result.get("synthesis_passed"),
            "precheck_issues": precheck_issues,
        },
        "evaluation_source": "hidden_oracle" if blind_eda_result else "agent_generated_testbench",
        "self_eda_summary": {
            "overall_pass": self_eda_result.get("overall_pass"),
            "simulation_passed": self_eda_result.get("simulation_passed"),
            "synthesis_passed": self_eda_result.get("synthesis_passed"),
        },
        "feedback_tags": list((state.get("feedback_report") or {}).get("error_tags") or []),
        "feedback_fingerprints": list((state.get("feedback_report") or {}).get("fingerprint_keys") or []),
        "output_dir": str(output_dir),
    }


def run_benchmark_suite(
    *,
    service: AgentTaskService,
    suite_dir: Path,
    output_dir: Path,
    mode: str = "fpga",
    dry_run: bool | None = None,
    metadata_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = list_benchmark_cases(suite_dir)
    case_results: list[dict[str, Any]] = []

    for case in cases:
        case_output_dir = output_dir / case.case_id
        request_metadata = dict(case.metadata)
        request_metadata.update(metadata_overrides or {})
        request_metadata["benchmark_case_id"] = case.case_id
        request_metadata["benchmark_suite_dir"] = str(suite_dir)
        request = AgentTaskRequest.from_task_file(
            task_file=case.task_file,
            output_dir=case_output_dir,
            mode=mode or case.mode,
            dry_run=case.dry_run if dry_run is None else dry_run,
            task_kind=case.task_kind,
            title=case.title,
            origin="benchmark",
            metadata=request_metadata,
        )
        try:
            execution = service.run_sync(request)
            if case.oracle_testbench is not None:
                if not case.oracle_testbench.is_file():
                    raise FileNotFoundError(f"Blind oracle testbench not found: {case.oracle_testbench}")
                rtl_path = resolve_delivery_path(case_output_dir, "rtl_code.v")
                if not rtl_path.is_file():
                    raise FileNotFoundError(f"Generated RTL not found: {rtl_path}")
                blind_result = run_prechecked_eda(
                    run_dir=case_output_dir / "blind_oracle",
                    repo_root=service.repo_root,
                    rtl_code=rtl_path.read_text(encoding="utf-8"),
                    testbench_code=case.oracle_testbench.read_text(encoding="utf-8"),
                    interface_contract="",
                )
                execution.workflow_state["blind_eda_result"] = blind_result
                ensure_delivery_directories(case_output_dir)
                (case_output_dir / structured_path("blind_eda_result.json")).write_text(
                    json.dumps(blind_result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            score_payload = score_benchmark_case(
                case,
                record=execution.record,
                state=execution.workflow_state,
            )
        except Exception as exc:
            failed_record = AgentTaskRecord.create(request).mark_failed(error=str(exc), model=None)
            score_payload = score_benchmark_case(case, record=failed_record, state={})
            score_payload["runtime_error"] = str(exc)
        ensure_delivery_directories(case_output_dir)
        (case_output_dir / structured_path("benchmark_score.json")).write_text(
            json.dumps(score_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        case_results.append(score_payload)

    average_score = round(sum(item["score"] for item in case_results) / len(case_results), 2) if case_results else 0.0
    passed_cases = sum(1 for item in case_results if item["passed"])
    report = {
        "suite_dir": str(suite_dir),
        "output_dir": str(output_dir),
        "case_count": len(case_results),
        "passed_cases": passed_cases,
        "average_score": average_score,
        "results": case_results,
    }
    (output_dir / "benchmark_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "benchmark_report.md").write_text(render_benchmark_report_markdown(report), encoding="utf-8")
    return report


def render_benchmark_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# FPGA 盲测报告",
        "",
        f"- 测试集目录：{report['suite_dir']}",
        f"- 输出目录：{report['output_dir']}",
        f"- 案例数量：{report['case_count']}",
        f"- 通过数量：{report['passed_cases']}",
        f"- 平均得分：{report['average_score']}",
        "",
        "## 分案例结果",
    ]
    for result in report.get("results") or []:
        lines.extend(
            [
                "",
                f"### {result['case_id']} - {result['title']}",
                f"- 得分：{result['score']}",
                f"- 是否通过：{'是' if result['passed'] else '否'}",
                f"- 任务状态：{result['task_status']}",
                f"- 修复次数：{result['repair_attempts']}",
                f"- 反馈标签：{', '.join(result.get('feedback_tags') or []) or '无'}",
                "- 检查项：",
            ]
        )
        for check in result.get("checks") or []:
            lines.append(
                f"  - {check['name']}：{'通过' if check['passed'] else '未通过'}（{check['detail']}）"
            )
    return "\n".join(lines).strip() + "\n"


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
