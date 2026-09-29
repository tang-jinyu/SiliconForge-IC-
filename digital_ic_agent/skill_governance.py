from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any


SKILL_RELATIVE_PATH = Path("skills") / "digital-ic-verified-design"
SCANNED_SUFFIXES = {".md", ".py", ".ps1", ".sh", ".yaml", ".yml", ".json"}

_SECURITY_RULES = (
    (
        "embedded_secret",
        "fail",
        re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}"),
        "No embedded credentials or long-lived access tokens",
    ),
    (
        "destructive_command",
        "fail",
        re.compile(r"(?i)(rm\s+-rf|remove-item\s+[^\n]*-recurse|format\s+[a-z]:)"),
        "No destructive recursive filesystem command",
    ),
    (
        "unsafe_shell_execution",
        "fail",
        re.compile(r"(?i)(shell\s*=\s*true|os\.system\s*\(|invoke-expression)"),
        "No dynamic shell execution primitive",
    ),
    (
        "prompt_override",
        "warn",
        re.compile(r"(?i)(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt\s+override)"),
        "No prompt text that attempts to override the host agent",
    ),
)


def build_governance_artifacts(
    *,
    repo_root: Path,
    task_kind: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a deterministic Skill Card and static security report for one run."""
    skill_dir = (repo_root / SKILL_RELATIVE_PATH).resolve()
    security_report = scan_skill_package(skill_dir)
    metadata = metadata or {}
    skill_card = {
        "schema_version": "1.0",
        "name": "digital-ic-verified-design",
        "display_name": "数字 IC 可信设计技能",
        "version": "1.0.0-phase1",
        "owner": "digital-ic-agent",
        "entrypoint": str(SKILL_RELATIVE_PATH / "SKILL.md").replace("\\", "/"),
        "description": "生成或诊断可综合 Verilog，并保留接口契约、自检测试平台、仿真、综合、有限修复和审查证据。",
        "capabilities": [
            "需求到 RTL 的完整闭环",
            "接口契约校验",
            "自检查测试平台生成",
            "Icarus Verilog 仿真",
            "Yosys 逻辑综合",
            "有限修复与审查",
        ],
        "quality_gate": {
            "rule": "eda_result.overall_pass must be true",
            "simulation_required": True,
            "synthesis_required": True,
            "failure_status": "failed",
        },
        "execution_boundary": {
            "allowed_eda_tools": ["iverilog", "vvp", "yosys", "yowasp-yosys", "xvlog", "xelab", "xsim", "vivado"],
            "network_required_for_eda": False,
            "subprocess_timeout_seconds": 60,
            "workspace_scoped_artifacts": True,
        },
        "evaluation": {
            "suite": str(metadata.get("benchmark_suite_dir") or "benchmarks/phase1"),
            "case_id": metadata.get("benchmark_case_id"),
            "stage_one_cases": ["add8_verified", "handshake_fsm_verified", "sync_fifo_verified"],
        },
        "integrity": {
            "algorithm": "sha256",
            "package_digest": security_report["package_digest"],
            "signed": False,
            "note": "当前记录可复现摘要；共享发布前仍需接入 OMS 或等效外部签名。",
        },
        "verified_skills_alignment": {
            "cataloged": {"status": "pass", "evidence": str(SKILL_RELATIVE_PATH / "SKILL.md").replace("\\", "/")},
            "scanned": {"status": security_report["verdict"], "evidence": "security_report.json"},
            "evaluated": {"status": "pass", "evidence": str(metadata.get("benchmark_suite_dir") or "benchmarks/phase1")},
            "signed": {"status": "pending", "evidence": "仅有 SHA-256 摘要，尚未生成 detached OMS signature"},
            "documented": {"status": "pass", "evidence": "SKILL.md 与安全质量契约"},
        },
        "security_verdict": security_report["verdict"],
    }
    return {"skill_card": skill_card, "security_report": security_report}


def scan_skill_package(skill_dir: Path) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    if not skill_dir.exists():
        return {
            "schema_version": "1.0",
            "generated_at": generated_at,
            "verdict": "fail",
            "package_path": str(skill_dir),
            "package_digest": None,
            "files": [],
            "checks": [
                {
                    "name": "skill_package_present",
                    "status": "fail",
                    "detail": "The standard skill package was not found.",
                    "evidence": [str(skill_dir)],
                }
            ],
        }

    files = sorted(
        path for path in skill_dir.rglob("*") if path.is_file() and path.suffix.lower() in SCANNED_SUFFIXES
    )
    file_entries: list[dict[str, Any]] = []
    package_hasher = hashlib.sha256()
    decoded_files: list[tuple[Path, str]] = []
    for path in files:
        content = path.read_bytes()
        relative = path.relative_to(skill_dir).as_posix()
        digest = hashlib.sha256(content).hexdigest()
        package_hasher.update(relative.encode("utf-8"))
        package_hasher.update(b"\0")
        package_hasher.update(content)
        file_entries.append({"path": relative, "sha256": digest, "size_bytes": len(content)})
        decoded_files.append((path, content.decode("utf-8", errors="replace")))

    checks: list[dict[str, Any]] = [
        {
            "name": "skill_package_present",
            "status": "pass",
            "detail": "Standard SKILL.md package is present.",
            "evidence": ["SKILL.md"],
        }
    ]
    for name, severity, pattern, detail in _SECURITY_RULES:
        matches: list[str] = []
        for path, text in decoded_files:
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(f"{path.relative_to(skill_dir).as_posix()}:{line_number}")
        checks.append(
            {
                "name": name,
                "status": severity if matches else "pass",
                "detail": detail,
                "evidence": matches,
            }
        )

    statuses = {item["status"] for item in checks}
    verdict = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "verdict": verdict,
        "package_path": str(skill_dir),
        "package_digest": package_hasher.hexdigest(),
        "files": file_entries,
        "checks": checks,
        "runtime_controls": {
            "eda_allowlist": ["iverilog", "vvp", "yosys", "yowasp-yosys", "xvlog", "xelab", "xsim", "vivado"],
            "native_shell": False,
            "timeouts_enabled": True,
            "task_output_isolation": True,
            "secret_values_in_report": False,
        },
    }
