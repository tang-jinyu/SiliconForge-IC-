from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True)
class FPGASkill:
    key: str
    title: str
    stages: tuple[str, ...]
    guardrails: tuple[str, ...]
    failure_modes: tuple[str, ...]


FPGA_SKILLS: tuple[FPGASkill, ...] = (
    FPGASkill(
        key="clock_reset_discipline",
        title="Clock and Reset Discipline",
        stages=("requirement_analysis", "architecture_design", "spec_generation", "rtl_generation", "repair", "review"),
        guardrails=(
            "Prefer one dominant clock domain for the FPGA flow unless the task explicitly requires CDC handling.",
            "Make reset polarity, reset style, and post-reset observable state explicit in the specification and RTL.",
            "Do not hide sequencing bugs behind asynchronous control tricks or gated clocks.",
        ),
        failure_modes=(
            "ambiguous reset behavior",
            "mixed reset conventions across helper logic",
            "gated-clock style control instead of clock-enable style control",
        ),
    ),
    FPGASkill(
        key="interface_contract_and_handshake",
        title="Interface Contract and Handshake Discipline",
        stages=("requirement_analysis", "spec_generation", "rtl_generation", "tb_generation", "repair", "review"),
        guardrails=(
            "Preserve the exact top-level module name, port list, widths, and direction contract.",
            "Define what ready, valid, busy, done, and error signals mean cycle-by-cycle before writing RTL.",
            "Keep command ingress and result egress behavior externally observable instead of inventing shortcut sideband ports.",
        ),
        failure_modes=(
            "interface drift between spec and RTL",
            "handshake pulses too short to sample reliably",
            "testbench stimulating hidden internal shortcuts instead of the public interface",
        ),
    ),
    FPGASkill(
        key="fsm_and_ownership",
        title="FSM and Register Ownership",
        stages=("architecture_design", "spec_generation", "rtl_generation", "repair", "review"),
        guardrails=(
            "Give each stateful register one owning process and define default behavior for each FSM branch.",
            "Prefer local state fixes over controller rewrites during repair.",
            "Treat busy, done, valid, and error outputs as contract-visible state, not transient internal transport events.",
        ),
        failure_modes=(
            "multiple always blocks driving one register",
            "state machine stuck in idle due to missing latch or handshake hold",
            "status outputs emitted as one-cycle pulses with no hold behavior",
        ),
    ),
    FPGASkill(
        key="arithmetic_width_and_signedness",
        title="Arithmetic Width and Signedness Discipline",
        stages=("spec_generation", "rtl_generation", "repair", "review"),
        guardrails=(
            "Size arithmetic, concatenation, comparison, and carry paths explicitly.",
            "Be intentional about signed versus unsigned interpretation; never rely on tool-default promotion for crypto or counter logic.",
            "Keep result buses stable and width-correct instead of silently truncating or repacking them.",
        ),
        failure_modes=(
            "carry bit lost by narrow addition",
            "signedness mismatch in compare or shift logic",
            "silent truncation on top-level result buses",
        ),
    ),
    FPGASkill(
        key="resource_inference_templates",
        title="Resource Inference and Local Helper Templates",
        stages=("architecture_design", "rtl_generation", "repair", "review"),
        guardrails=(
            "Use inference-friendly templates for counters, RAMs, ROMs, FIFOs, and simple arithmetic helpers.",
            "If helper logic is small, inline it; if helper modules are instantiated, include the full synthesizable definition in the same file.",
            "Do not introduce black-box wrappers or ASIC-style placeholders into the FPGA MVP path.",
        ),
        failure_modes=(
            "undefined helper module instantiations",
            "RAM or FIFO logic coded in a way that breaks FPGA inference",
            "structural shells with no local implementation detail",
        ),
    ),
    FPGASkill(
        key="latency_and_observability",
        title="Latency Budget and Observability",
        stages=("spec_generation", "rtl_generation", "tb_generation", "repair", "review"),
        guardrails=(
            "State the expected latency model or completion condition for each command path.",
            "Hold completion and result signals long enough for an external checker or controller to observe them deterministically.",
            "Keep simulation duration assumptions aligned with the actual command count and latency budget.",
        ),
        failure_modes=(
            "simulation timeout because command latency is not budgeted",
            "result_valid or done drops before the testbench can sample it",
            "status and result buses updated in the same edge they are consumed as if they were combinational",
        ),
    ),
    FPGASkill(
        key="tb_external_stimulus_and_selfcheck",
        title="External Stimulus and Self-Checking Testbench",
        stages=("tb_generation", "repair", "review"),
        guardrails=(
            "Drive the DUT through the declared public interface instead of hidden internal command wires.",
            "Keep the testbench deterministic, self-checking, and compatible with Icarus Verilog.",
            "Check only testbench-visible outputs and externally meaningful handshakes unless the interface explicitly exposes internal state.",
        ),
        failure_modes=(
            "direct injection through disconnected cmd_valid-style signals",
            "testbench redefining the DUT module instead of wrapping it",
            "nondeterministic checks tied to hidden internal state",
        ),
    ),
    FPGASkill(
        key="repair_root_cause_locality",
        title="Repair Root-Cause Locality",
        stages=("repair", "review"),
        guardrails=(
            "When synthesis already passes, repair the smallest local control or datapath defect that explains the failing behavior.",
            "Use logs and precheck evidence to identify the first broken observable in the chain instead of rewriting the architecture.",
            "Preserve the top-level interface and visible behavior unless logs prove a contract contradiction.",
        ),
        failure_modes=(
            "repair rewrites the whole controller instead of fixing the first broken latch or transition",
            "fixes chase symptoms rather than the first failing handshake or assignment discipline",
            "repair changes the top-level contract while trying to silence EDA errors",
        ),
    ),
)


def list_fpga_skills(*, stage: str | None = None) -> list[FPGASkill]:
    if stage is None:
        return list(FPGA_SKILLS)
    return [skill for skill in FPGA_SKILLS if stage in skill.stages]


def build_fpga_skill_prompt(*, stage: str | None = None) -> str:
    skills = list_fpga_skills(stage=stage)
    if not skills:
        return ""

    skill_blocks = []
    for skill in skills:
        guardrails = "\n".join(f"- {item}" for item in skill.guardrails)
        failure_modes = "\n".join(f"- {item}" for item in skill.failure_modes)
        skill_blocks.append(
            dedent(
                f"""
                [{skill.title}]
                Guardrails:
                {guardrails}
                Common failure modes:
                {failure_modes}
                """
            ).strip()
        )

    return dedent(
        """
        FPGA skill pack:
        Apply the following engineering skills as hard guardrails rather than optional style advice.
        """
    ).strip() + "\n\n" + "\n\n".join(skill_blocks)