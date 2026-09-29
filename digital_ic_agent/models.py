from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class StructuredStageOutput(BaseModel):
    task_summary: str = Field(..., description="Condensed task summary")
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    performance_targets: list[str] = Field(default_factory=list)
    technical_risks: list[str] = Field(default_factory=list)
    questions_to_clarify: list[str] = Field(default_factory=list)


class WorkflowState(TypedDict, total=False):
    request: str
    task_file: str
    mode: str
    task_kind: str
    run_dir: str
    interface_contract: str
    requirement_analysis: dict
    architecture_design: dict
    specification: str
    rtl_code: str
    testbench_code: str
    eda_result: dict
    repair_attempts: int
    repair_response: str
    repair_history: list[dict]
    review: dict
    llm_trace: dict
    execution_path: str
