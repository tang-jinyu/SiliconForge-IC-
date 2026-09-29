from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .code_utils import tail_text
from .fpga_skills import FPGA_SKILLS
from .task_models import AgentTaskRecord


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FeedbackRule:
    tag: str
    skill_key: str
    match_text: str
    lesson: str


@dataclass(frozen=True)
class SemanticFingerprintDefinition:
    key: str
    title: str
    skill_key: str
    trigger_patterns: tuple[str, ...]
    failure_patterns: tuple[str, ...]
    summary: str


FEEDBACK_RULES: tuple[FeedbackRule, ...] = (
    FeedbackRule(
        tag="interface_contract_mismatch",
        skill_key="interface_contract_and_handshake",
        match_text="Interface contract mismatch",
        lesson="Preserve the exact top-level module header and visible handshake contract before changing internals.",
    ),
    FeedbackRule(
        tag="undefined_helper_module",
        skill_key="resource_inference_templates",
        match_text="Undefined instantiated modules",
        lesson="Inline small helpers or include the full same-file synthesizable helper definition instead of leaving wrappers undefined.",
    ),
    FeedbackRule(
        tag="undriven_internal_wire",
        skill_key="resource_inference_templates",
        match_text="undriven internal wire",
        lesson="Every consumed internal wire needs a same-file driver; do not leave local helper plumbing half-connected.",
    ),
    FeedbackRule(
        tag="sequential_blocking_assignment",
        skill_key="fsm_and_ownership",
        match_text="blocking assignments in edge-sensitive always blocks",
        lesson="Use nonblocking assignments for sequential logic and keep each state register under one owning process.",
    ),
    FeedbackRule(
        tag="combinational_nonblocking_assignment",
        skill_key="fsm_and_ownership",
        match_text="nonblocking assignments in combinational always blocks",
        lesson="Use blocking assignments plus explicit defaults in combinational always blocks.",
    ),
    FeedbackRule(
        tag="multiple_procedural_drivers",
        skill_key="fsm_and_ownership",
        match_text="same procedural target from multiple always blocks",
        lesson="Consolidate each stateful register into a single owner always block.",
    ),
    FeedbackRule(
        tag="rtl_delay_control",
        skill_key="clock_reset_discipline",
        match_text="delay controls (#)",
        lesson="Do not rely on delay controls in synthesizable RTL; express timing with counters or FSM state.",
    ),
    FeedbackRule(
        tag="tb_direct_injection",
        skill_key="tb_external_stimulus_and_selfcheck",
        match_text="detected disconnected direct-command stimulus signals",
        lesson="Drive commands through the declared external ingress path instead of hidden command wires.",
    ),
    FeedbackRule(
        tag="tb_sim_duration_too_short",
        skill_key="latency_and_observability",
        match_text="SIM_DURATION=",
        lesson="Budget simulation time from command count and expected latency instead of guessing a short timeout.",
    ),
    FeedbackRule(
        tag="tb_redefines_dut",
        skill_key="tb_external_stimulus_and_selfcheck",
        match_text="redefines DUT module",
        lesson="Keep the testbench as a separate wrapper module; never redefine the DUT top module in the bench.",
    ),
    FeedbackRule(
        tag="simulation_syntax_error",
        skill_key="repair_root_cause_locality",
        match_text="syntax error",
        lesson="Fix the first syntax or parser breakage before attempting semantic repair.",
    ),
    FeedbackRule(
        tag="simulation_self_check_failure",
        skill_key="latency_and_observability",
        match_text="FAIL:",
        lesson="When self-checking simulation fails after synthesis passes, trace the first broken visible handshake or result-hold condition.",
    ),
)


SEMANTIC_FINGERPRINTS: tuple[SemanticFingerprintDefinition, ...] = (
    SemanticFingerprintDefinition(
        key="handshake_contract_surface",
        title="Handshake Contract Surface",
        skill_key="interface_contract_and_handshake",
        trigger_patterns=(r"\bready\b", r"\bvalid\b", r"\bbusy\b", r"\back\b", r"\bstart\b", r"cmd_ready", r"result_valid"),
        failure_patterns=(r"interface contract", r"FAIL:", r"busy", r"valid", r"ack"),
        summary="Define and preserve cycle-level handshake meaning before adjusting local control logic.",
    ),
    SemanticFingerprintDefinition(
        key="endian_byte_order",
        title="Endian and Byte Order",
        skill_key="arithmetic_width_and_signedness",
        trigger_patterns=(r"little-endian", r"big-endian", r"\bendian\b", r"byte order", r"\bmsb\b", r"\blsb\b"),
        failure_patterns=(r"FAIL:", r"mismatch", r"result", r"resp_data", r"result_data"),
        summary="Make byte ordering explicit across interface packing, storage layout, and visible result buses.",
    ),
    SemanticFingerprintDefinition(
        key="carry_borrow_path",
        title="Carry and Borrow Path",
        skill_key="arithmetic_width_and_signedness",
        trigger_patterns=(r"\bcarry\b", r"\bborrow\b", r"\bcout\b", r"\bcin\b", r"subtractor", r"adder", r"addsub", r"carry_borrow"),
        failure_patterns=(r"FAIL:", r"mismatch", r"carry", r"borrow", r"sum", r"overflow"),
        summary="Extend arithmetic one bit wider than the visible datapath and define carry or borrow semantics explicitly.",
    ),
    SemanticFingerprintDefinition(
        key="signedness_control",
        title="Signedness Control",
        skill_key="arithmetic_width_and_signedness",
        trigger_patterns=(r"\bsigned\b", r"\bunsigned\b", r"\$signed", r"\$unsigned", r">>>", r"arithmetic shift"),
        failure_patterns=(r"FAIL:", r"mismatch", r"compare", r"shift", r"negative"),
        summary="Do not rely on tool-default signed promotion; state signedness intent in the spec and RTL.",
    ),
    SemanticFingerprintDefinition(
        key="state_hold_visibility",
        title="State Hold and Observability",
        skill_key="latency_and_observability",
        trigger_patterns=(r"cmd_busy", r"result_valid", r"resp_valid", r"done", r"fault_detect", r"error_flag", r"status_code"),
        failure_patterns=(r"FAIL:", r"never asserts", r"stuck", r"busy", r"valid", r"done"),
        summary="Hold contract-visible status and result signals long enough for external sampling instead of emitting transient pulses.",
    ),
    SemanticFingerprintDefinition(
        key="error_path_determinism",
        title="Error Path Determinism",
        skill_key="repair_root_cause_locality",
        trigger_patterns=(r"error", r"fault", r"illegal", r"unsupported", r"status_code", r"error_code", r"fault_detect"),
        failure_patterns=(r"FAIL:", r"fault", r"error", r"unsupported", r"illegal"),
        summary="Drive error and fault outcomes deterministically through one visible path instead of same-edge self-sampling tricks.",
    ),
    SemanticFingerprintDefinition(
        key="ram_fifo_inference",
        title="RAM or FIFO Inference",
        skill_key="resource_inference_templates",
        trigger_patterns=(r"\bfifo\b", r"\bram\b", r"\bmemory\b", r"wr_ptr", r"rd_ptr", r"buffer", r"dout", r"din"),
        failure_patterns=(r"Undefined instantiated modules", r"undriven internal wire", r"FAIL:", r"full", r"empty"),
        summary="Keep storage logic inference-friendly and local instead of hiding it behind undefined wrappers or ambiguous read-write behavior.",
    ),
    SemanticFingerprintDefinition(
        key="public_serial_stimulus",
        title="Public Serial Stimulus",
        skill_key="tb_external_stimulus_and_selfcheck",
        trigger_patterns=(r"\bspi\b", r"\buart\b", r"serial", r"spi_cs_n", r"spi_sclk", r"uart_rx"),
        failure_patterns=(r"direct-command stimulus", r"FAIL:", r"spi", r"uart", r"syntax error"),
        summary="Stimulate serial ingress through the exposed pins and timing model rather than invented helper wires in the testbench.",
    ),
)


class FeedbackLoop:
    def __init__(self, repo_root: Path, *, history_limit: int = 200) -> None:
        self.repo_root = repo_root
        self.history_limit = history_limit
        self.memory_dir = repo_root / "project_prompt" / "output"
        self.memory_json_path = self.memory_dir / "fpga_feedback_memory.json"
        self.memory_markdown_path = self.memory_dir / "fpga_feedback_memory.md"

    def _build_semantic_fingerprints(
        self,
        *,
        record: AgentTaskRecord,
        state: dict[str, Any],
        error: str | None,
        matched_rules: list[FeedbackRule],
    ) -> list[dict[str, str]]:
        outcome = self._infer_outcome(state=state, error=error)
        if outcome == "pass":
            return []

        context_text = "\n".join(
            filter(
                None,
                [
                    record.request.requirement_text,
                    str(state.get("specification") or ""),
                    str(state.get("rtl_code") or ""),
                    str(state.get("testbench_code") or ""),
                ],
            )
        )
        failure_text = "\n".join(
            filter(
                None,
                [
                    error or "",
                    "\n".join((state.get("eda_result") or {}).get("precheck_issues") or []),
                    str((state.get("eda_result") or {}).get("simulation_log") or ""),
                    str((state.get("eda_result") or {}).get("yosys_log") or ""),
                    " ".join(rule.tag for rule in matched_rules),
                ],
            )
        )

        fingerprints: list[dict[str, str]] = []
        for definition in SEMANTIC_FINGERPRINTS:
            trigger_match = _find_first_regex_match(context_text, definition.trigger_patterns)
            if trigger_match is None:
                continue
            failure_match = _find_first_regex_match(failure_text, definition.failure_patterns)
            if failure_match is None and outcome in {
                "precheck_failure",
                "simulation_failure",
                "synthesis_failure",
                "runtime_failure",
                "unknown_failure",
            }:
                failure_match = _find_first_regex_match(failure_text or definition.title, (r".+",))
            if failure_match is None:
                continue
            fingerprints.append(
                {
                    "key": definition.key,
                    "title": definition.title,
                    "skill_key": definition.skill_key,
                    "evidence": f"Context: {trigger_match}; Failure: {failure_match}",
                    "summary": definition.summary,
                }
            )

        return fingerprints

    def _update_memory(self, report: dict[str, Any]) -> dict[str, Any]:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        memory_payload = self._load_memory_payload()

        if report.get("error_tags") or report.get("fingerprint_keys"):
            entry = {
                "task_id": report["task_id"],
                "task_title": report["task_title"],
                "task_kind": report["task_kind"],
                "captured_at": report["captured_at"],
                "outcome": report["outcome"],
                "skill_categories": report["skill_categories"],
                "error_tags": report["error_tags"],
                "fingerprint_keys": report.get("fingerprint_keys") or [],
                "recommended_guardrails": report["recommended_guardrails"],
            }
            entries = list(memory_payload.get("entries") or [])
            entries.append(entry)
            memory_payload["entries"] = entries[-self.history_limit :]

        memory_payload["updated_at"] = _utcnow_iso()
        skill_counter = Counter()
        tag_counter = Counter()
        fingerprint_counter = Counter()
        for entry in memory_payload.get("entries") or []:
            skill_counter.update(entry.get("skill_categories") or [])
            tag_counter.update(entry.get("error_tags") or [])
            fingerprint_counter.update(entry.get("fingerprint_keys") or [])

        memory_payload["skill_counts"] = dict(skill_counter)
        memory_payload["tag_counts"] = dict(tag_counter)
        memory_payload["fingerprint_counts"] = dict(fingerprint_counter)
        self.memory_json_path.write_text(json.dumps(memory_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        markdown_text = self._render_memory_markdown(memory_payload)
        self.memory_markdown_path.write_text(markdown_text, encoding="utf-8")

        return {
            "memory_path": str(self.memory_json_path),
            "memory_markdown_path": str(self.memory_markdown_path),
            "entry_count": len(memory_payload.get("entries") or []),
            "top_tags": [
                {"tag": tag, "count": count}
                for tag, count in tag_counter.most_common(5)
            ],
            "top_skill_categories": [
                {"skill": skill_key, "count": count}
                for skill_key, count in skill_counter.most_common(5)
            ],
            "top_fingerprints": [
                {"fingerprint": fingerprint_key, "count": count}
                for fingerprint_key, count in fingerprint_counter.most_common(5)
            ],
        }

    def _load_memory_payload(self) -> dict[str, Any]:
        if not self.memory_json_path.exists():
            return {
                "updated_at": None,
                "entries": [],
                "skill_counts": {},
                "tag_counts": {},
                "fingerprint_counts": {},
            }
        try:
            payload = json.loads(self.memory_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "updated_at": None,
                "entries": [],
                "skill_counts": {},
                "tag_counts": {},
                "fingerprint_counts": {},
            }
        payload.setdefault("entries", [])
        payload.setdefault("skill_counts", {})
        payload.setdefault("tag_counts", {})
        payload.setdefault("fingerprint_counts", {})
        return payload

    def _render_memory_markdown(self, payload: dict[str, Any]) -> str:
        skill_title_map = {skill.key: skill.title for skill in FPGA_SKILLS}
        entries = list(payload.get("entries") or [])
        tag_counter = Counter(payload.get("tag_counts") or {})
        skill_counter = Counter(payload.get("skill_counts") or {})
        fingerprint_counter = Counter(payload.get("fingerprint_counts") or {})

        lines = [
            "Learned FPGA failure memory for prompt injection.",
            f"Updated at: {payload.get('updated_at')}",
            f"Tracked failure observations: {len(entries)}",
            "",
            "Top recurring failure tags:",
        ]
        if tag_counter:
            for tag, count in tag_counter.most_common(5):
                lines.append(f"- {tag}: {count}")
        else:
            lines.append("- No recurring failure tags collected yet.")

        lines.extend([
            "",
            "Top skill categories needing reinforcement:",
        ])
        if skill_counter:
            for skill_key, count in skill_counter.most_common(5):
                lines.append(f"- {skill_title_map.get(skill_key, skill_key)}: {count}")
        else:
            lines.append("- No reinforced skill categories collected yet.")

        lines.extend([
            "",
            "Top semantic fingerprints:",
        ])
        if fingerprint_counter:
            for fingerprint_key, count in fingerprint_counter.most_common(5):
                lines.append(f"- {fingerprint_key}: {count}")
        else:
            lines.append("- No semantic fingerprints collected yet.")

        lines.extend([
            "",
            "Recent corrective guardrails:",
        ])
        recent_guardrails: list[str] = []
        for entry in reversed(entries[-5:]):
            for guardrail in entry.get("recommended_guardrails") or []:
                if guardrail not in recent_guardrails:
                    recent_guardrails.append(guardrail)
        if recent_guardrails:
            for guardrail in recent_guardrails[:6]:
                lines.append(f"- {guardrail}")
        else:
            lines.append("- No corrective guardrails collected yet.")

        return "\n".join(lines).strip() + "\n"

    def capture(
        self,
        *,
        record: AgentTaskRecord,
        state: dict[str, Any],
        error: str | None = None,
    ) -> dict[str, Any]:
        report = self._build_feedback_report(record=record, state=state, error=error)
        snapshot = self._update_memory(report)
        return {
            "feedback_report": report,
            "feedback_memory_snapshot": snapshot,
        }

    def _build_feedback_report(
        self,
        *,
        record: AgentTaskRecord,
        state: dict[str, Any],
        error: str | None,
    ) -> dict[str, Any]:
        eda_result = dict(state.get("eda_result") or {})
        precheck_issues = list(eda_result.get("precheck_issues") or [])
        specification = str(state.get("specification") or "")
        rtl_code = str(state.get("rtl_code") or "")
        testbench_code = str(state.get("testbench_code") or "")
        simulation_log_tail = tail_text(eda_result.get("simulation_log", ""), max_chars=1200)
        yosys_log_tail = tail_text(eda_result.get("yosys_log", ""), max_chars=1200)
        observations = [item for item in precheck_issues if item]
        if error:
            observations.append(error)
        if simulation_log_tail:
            observations.append(simulation_log_tail)
        if yosys_log_tail and yosys_log_tail != simulation_log_tail:
            observations.append(yosys_log_tail)

        matched_rules: list[FeedbackRule] = []
        lowered_observations = "\n".join(observations).lower()
        for rule in FEEDBACK_RULES:
            if rule.match_text.lower() in lowered_observations:
                matched_rules.append(rule)

        if not matched_rules and error:
            matched_rules.append(
                FeedbackRule(
                    tag="runtime_exception",
                    skill_key="repair_root_cause_locality",
                    match_text="runtime exception",
                    lesson="Stabilize the first runtime exception and preserve partial artifacts for diagnosis before widening the repair scope.",
                )
            )

        if not matched_rules and eda_result and not eda_result.get("overall_pass"):
            matched_rules.append(
                FeedbackRule(
                    tag="unknown_fpga_failure",
                    skill_key="repair_root_cause_locality",
                    match_text="unknown failure",
                    lesson="Capture the first reproducible failing observable and add a dedicated rule once the pattern repeats.",
                )
            )

        skill_keys = []
        for rule in matched_rules:
            if rule.skill_key not in skill_keys:
                skill_keys.append(rule.skill_key)

        recommended_guardrails = []
        for rule in matched_rules:
            if rule.lesson not in recommended_guardrails:
                recommended_guardrails.append(rule.lesson)

        semantic_fingerprints = self._build_semantic_fingerprints(
            record=record,
            state=state,
            error=error,
            matched_rules=matched_rules,
        )
        for fingerprint in semantic_fingerprints:
            if fingerprint["skill_key"] not in skill_keys:
                skill_keys.append(fingerprint["skill_key"])
            if fingerprint["summary"] not in recommended_guardrails:
                recommended_guardrails.append(fingerprint["summary"])

        return {
            "task_id": record.task_id,
            "task_title": record.request.title,
            "task_kind": record.request.task_kind,
            "status": record.status,
            "captured_at": _utcnow_iso(),
            "mode": record.request.mode,
            "outcome": self._infer_outcome(state=state, error=error),
            "skill_categories": skill_keys,
            "error_tags": [rule.tag for rule in matched_rules],
            "semantic_fingerprints": semantic_fingerprints,
            "fingerprint_keys": [fingerprint["key"] for fingerprint in semantic_fingerprints],
            "recommended_guardrails": recommended_guardrails,
            "repair_attempts": int(state.get("repair_attempts", 0)),
            "top_module": eda_result.get("top_module"),
            "source_summary": {
                "requirement_text": tail_text(record.request.requirement_text, max_chars=800),
                "specification": tail_text(specification, max_chars=800),
                "rtl_code": tail_text(rtl_code, max_chars=800),
                "testbench_code": tail_text(testbench_code, max_chars=800),
                "precheck_issues": precheck_issues,
                "simulation_log_tail": simulation_log_tail,
                "yosys_log_tail": yosys_log_tail,
                "error": error,
            },
        }

    @staticmethod
    def _infer_outcome(*, state: dict[str, Any], error: str | None) -> str:
        if error:
            return "runtime_failure"
        eda_result = dict(state.get("eda_result") or {})
        if not eda_result:
            return "no_eda_result"
        if eda_result.get("overall_pass"):
            return "pass"
        if eda_result.get("precheck_issues"):
            return "precheck_failure"
        if not eda_result.get("simulation_passed"):
            return "simulation_failure"
        if not eda_result.get("synthesis_passed"):
            return "synthesis_failure"
        return "unknown_failure"


def _find_first_regex_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _snippet_around_match(text, match.start(), match.end())
    return None


def _snippet_around_match(text: str, start: int, end: int, *, radius: int = 72) -> str:
    left = max(start - radius, 0)
    right = min(end + radius, len(text))
    return " ".join(text[left:right].split())