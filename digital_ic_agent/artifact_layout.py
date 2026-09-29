from __future__ import annotations

from pathlib import Path


DELIVERY_PATHS: dict[str, str] = {
    "task_input.md": "doc/task_input.md",
    "requirement_analysis.json": "doc/requirement_analysis.json",
    "architecture_design.json": "doc/architecture_design.json",
    "specification.md": "doc/specification.md",
    "delivery_report.md": "doc/delivery_report.md",
    "review.json": "doc/review.json",
    "rtl_code.v": "rtl/rtl_code.v",
    "testbench.v": "tb/testbench.v",
    "eda_result.json": "doc/eda_result.json",
    "feedback_report.json": "doc/feedback_report.json",
    "feedback_memory_snapshot.json": "doc/feedback_memory_snapshot.json",
    "skill_card.json": "doc/skill_card.json",
    "security_report.json": "doc/security_report.json",
    "simulation.log": "logs/simulation.log",
    "yosys.log": "logs/yosys.log",
    "repair_response.md": "logs/repair_response.md",
    "repair_history.json": "logs/repair_history.json",
    "llm_trace.json": "meta/llm_trace.json",
    "run_manifest.json": "meta/run_manifest.json",
    "benchmark_score.json": "meta/benchmark_score.json",
    "blind_eda_result.json": "doc/blind_eda_result.json",
}

EDITABLE_DELIVERY_PATHS = {
    "rtl/rtl_code.v",
    "tb/testbench.v",
    "doc/specification.md",
    "doc/delivery_report.md",
}


def structured_path(file_name: str) -> str:
    normalized = file_name.replace("\\", "/").lstrip("/")
    return DELIVERY_PATHS.get(normalized, normalized)


def legacy_path(file_name: str) -> str | None:
    normalized = file_name.replace("\\", "/").lstrip("/")
    for legacy, structured in DELIVERY_PATHS.items():
        if structured == normalized:
            return legacy
    return None


def resolve_delivery_path(output_dir: Path, file_name: str) -> Path:
    """Resolve a structured artifact path with read-only legacy fallback."""
    normalized = file_name.replace("\\", "/").lstrip("/")
    candidate = output_dir / structured_path(normalized)
    if candidate.exists():
        return candidate
    fallback = legacy_path(normalized)
    if fallback:
        legacy_candidate = output_dir / fallback
        if legacy_candidate.exists():
            return legacy_candidate
    direct = output_dir / normalized
    return direct


def ensure_delivery_directories(output_dir: Path) -> None:
    for directory in ("rtl", "tb", "doc", "logs", "meta", "eda"):
        (output_dir / directory).mkdir(parents=True, exist_ok=True)
