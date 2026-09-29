from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TaskExecutionStrategy = Literal["workflow", "eda_triage", "interface_contract_check"]


@dataclass(frozen=True)
class TaskKindDefinition:
    key: str
    title: str
    description: str
    execution_strategy: TaskExecutionStrategy
    input_hint: str
    gallery_title: str
    gallery_caption: str
    request_preamble: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "execution_strategy": self.execution_strategy,
            "input_hint": self.input_hint,
            "gallery_title": self.gallery_title,
            "gallery_caption": self.gallery_caption,
            "request_preamble": self.request_preamble,
        }


TASK_KIND_DEFINITIONS = {
    "digital_ic_workflow": TaskKindDefinition(
        key="digital_ic_workflow",
        title="完整数字 IC 闭环",
        description="从需求分析一路生成规格、RTL、TB、EDA 与 repair。适合作为完整任务入口。",
        execution_strategy="workflow",
        input_hint="输入需求文本或任务文件。",
        gallery_title="Full Flow Atelier",
        gallery_caption="从任务文本到 RTL 与 EDA 的完整自动化工作流。",
    ),
    "rtl_module_generation": TaskKindDefinition(
        key="rtl_module_generation",
        title="模块生成",
        description="聚焦某个模块或子系统的规格、RTL 和最小可验证 testbench 生成。",
        execution_strategy="workflow",
        input_hint="输入模块目标、接口约束、时序/资源目标。",
        gallery_title="Module Bloom",
        gallery_caption="适合快速生成一个可综合模块与配套最小验证骨架。",
        request_preamble=(
            "Task type: RTL module generation. Focus on producing a synthesizable module or subsystem, "
            "a concise implementable specification, and a minimal deterministic self-checking testbench. "
            "Prefer local module boundaries over system-level architectural expansion."
        ),
    ),
    "tb_repair": TaskKindDefinition(
        key="tb_repair",
        title="TB 修复",
        description="优先修复 testbench 的语法、事件顺序、接口驱动和自检逻辑，除非日志明确证明 RTL 有错。",
        execution_strategy="workflow",
        input_hint="输入 failing case、RTL/TB、日志或复现描述。",
        gallery_title="Bench Polishing",
        gallery_caption="把失配的 testbench 拉回到可复现、可自检、可迭代的状态。",
        request_preamble=(
            "Task type: testbench repair. Prioritize fixing the testbench, event ordering, protocol stimulus, "
            "and self-check semantics. Keep RTL stable unless the failing logs directly prove the RTL is wrong."
        ),
    ),
    "eda_triage": TaskKindDefinition(
        key="eda_triage",
        title="EDA Triage",
        description="对既有 RTL/TB 做预检、仿真和综合检查，生成问题摘要而不重新生成整个设计。",
        execution_strategy="eda_triage",
        input_hint="通过 metadata 传入 rtl_code 或 rtl_path，以及 testbench_code 或 testbench_path。",
        gallery_title="Signal Triage",
        gallery_caption="专注于把已有样本快速送进 precheck、仿真与综合闭环。",
    ),
    "interface_contract_check": TaskKindDefinition(
        key="interface_contract_check",
        title="已有 RTL 接口校验",
        description="独立诊断已有 RTL 与既有 interface contract；完整闭环会自行设计接口，不需要使用此入口。",
        execution_strategy="interface_contract_check",
        input_hint="通过 metadata 传入 rtl_code 或 rtl_path，并提供 contract_path 或 task_file。",
        gallery_title="Contract Mirror",
        gallery_caption="对已有工程快速检查 top-level 模块名、端口声明与契约是否一致。",
    ),
}

DEFAULT_TASK_KIND = "digital_ic_workflow"


def get_task_kind_definition(task_kind: str) -> TaskKindDefinition:
    try:
        return TASK_KIND_DEFINITIONS[task_kind]
    except KeyError as exc:
        supported = ", ".join(sorted(TASK_KIND_DEFINITIONS))
        raise ValueError(f"Unsupported task kind: {task_kind}. Supported kinds: {supported}.") from exc


def list_task_kind_definitions() -> list[TaskKindDefinition]:
    return [TASK_KIND_DEFINITIONS[key] for key in sorted(TASK_KIND_DEFINITIONS)]


def list_task_kind_keys() -> list[str]:
    return sorted(TASK_KIND_DEFINITIONS)


def build_effective_request_text(task_kind: str, requirement_text: str) -> str:
    definition = get_task_kind_definition(task_kind)
    if not definition.request_preamble:
        return requirement_text
    return definition.request_preamble + "\n\n" + requirement_text
