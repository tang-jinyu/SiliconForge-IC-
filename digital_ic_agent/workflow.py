from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .code_utils import (
    extract_code_blocks,
    extract_repair_artifacts,
    extract_verilog_code,
    sanitize_verilog_rtl,
    sanitize_verilog_testbench,
    tail_text,
)
from .arithmetic_skill import (
    build_multiplier_analysis,
    build_multiplier_architecture,
    build_multiplier_review,
    build_multiplier_rtl,
    build_multiplier_spec,
    build_multiplier_testbench,
    detect_multiplier_contract,
)
from .code_utils import (
    extract_module_header,
    infer_top_module_name,
    normalize_module_header,
)
from .config import AppConfig
from .eda import run_eda_checks
from .llm import ExternalAPILLM
from .models import StructuredStageOutput, WorkflowState
from .prechecks import load_interface_contract, run_prechecked_eda
from .prompt_loader import PromptLibrary
from .rules import (
    build_repair_constraints,
    build_rtl_generation_guidance,
    build_tb_generation_guidance,
)


def run_workflow(
    request: str,
    task_file: Path,
    config: AppConfig,
    run_dir: Path,
    task_kind: str = "digital_ic_workflow",
    cancellation_check: Callable[[str], None] | None = None,
    stage_checkpoint: Callable[[str, dict[str, Any] | None], None] | None = None,
    llm_trace_update: Callable[[dict[str, Any]], None] | None = None,
) -> WorkflowState:
    prompt_library = PromptLibrary(config.project_prompt_dir)
    llm = None if config.dry_run else ExternalAPILLM(
        config,
        cancellation_check=cancellation_check,
        trace_update=llm_trace_update,
    )
    graph = _build_graph(
        config,
        prompt_library,
        llm,
        cancellation_check=cancellation_check,
        stage_checkpoint=stage_checkpoint,
    )
    interface_contract = load_interface_contract(task_file)
    return graph.invoke(
        {
            "request": request,
            "task_file": str(task_file),
            "mode": config.mode,
            "task_kind": task_kind,
            "run_dir": str(run_dir),
            "interface_contract": interface_contract,
            "repair_attempts": 0,
        }
    )


def _build_graph(
    config: AppConfig,
    prompt_library: PromptLibrary,
    llm: ExternalAPILLM | None,
    *,
    cancellation_check: Callable[[str], None] | None,
    stage_checkpoint: Callable[[str, dict[str, Any] | None], None] | None,
):
    graph = StateGraph(WorkflowState)

    def checkpoint(stage: str, updates: dict[str, Any] | None = None) -> None:
        if cancellation_check is not None:
            cancellation_check(stage)
        if stage_checkpoint is not None:
            stage_checkpoint(stage, updates)

    def requirement_analysis_node(state: WorkflowState) -> WorkflowState:
        checkpoint("analyze_requirement:start")
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            artifact = build_multiplier_analysis(multiplier_contract)
        elif config.dry_run:
            artifact = _dry_requirement_analysis(state["request"])
        else:
            system_prompt = prompt_library.build_stage_system_prompt(
                stage="requirement_analysis",
                role_instruction=(
                    "You are a digital IC competition analyst. Focus on FPGA feasibility, engineering "
                    "constraints, and output only the schema requested."
                ),
            )
            user_prompt = dedent(
                f"""
                Analyze the following task for a single-FPGA MVP.

                Task:
                {state['request']}

                Output must focus on what the agent needs to build next.
                """
            ).strip()
            artifact = llm.invoke_structured(
                system_prompt,
                user_prompt,
                StructuredStageOutput,
                operation_label="analyze_requirement:llm",
            )
        updates = {"requirement_analysis": artifact.model_dump()}
        if multiplier_contract is not None:
            updates["execution_path"] = "deterministic_multiplier_skill"
        checkpoint("analyze_requirement:complete", updates)
        return updates

    def architecture_design_node(state: WorkflowState) -> WorkflowState:
        checkpoint("design_architecture:start")
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            artifact = build_multiplier_architecture(multiplier_contract)
        elif config.dry_run:
            artifact = _dry_architecture_design(state["request"], state["requirement_analysis"])
        else:
            system_prompt = prompt_library.build_stage_system_prompt(
                stage="architecture_design",
                role_instruction=(
                    "You are a senior FPGA architecture designer. Convert structured requirements into a "
                    "hardware-oriented agent architecture plan and output only the schema requested."
                ),
            )
            user_prompt = dedent(
                f"""
                Build an architecture design for the following single-FPGA digital IC agent task.

                Original task:
                {state['request']}

                Requirement analysis:
                {json.dumps(state['requirement_analysis'], ensure_ascii=False, indent=2)}

                The output should help a LangGraph-based implementation proceed cleanly.
                """
            ).strip()
            artifact = llm.invoke_structured(
                system_prompt,
                user_prompt,
                StructuredStageOutput,
                operation_label="design_architecture:llm",
            )
        updates = {"architecture_design": artifact.model_dump()}
        checkpoint("design_architecture:complete", updates)
        return updates

    def spec_generation_node(state: WorkflowState) -> WorkflowState:
        checkpoint("generate_spec:start")
        spec_input = _compose_spec_input(state)
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            specification = build_multiplier_spec(multiplier_contract)
        elif config.dry_run:
            specification = _dry_specification(spec_input)
        else:
            system_prompt = prompt_library.build_stage_system_prompt(
                stage="spec_generation",
                role_instruction="You are a hardware specification writer for FPGA-oriented RTL work.",
            )
            user_prompt = prompt_library.format("spec_generation", user_requirement=spec_input)
            specification = llm.invoke_text(
                system_prompt,
                user_prompt,
                operation_label="generate_spec:llm",
            )
        updates = {"specification": specification}
        checkpoint("generate_spec:complete", updates)
        return updates

    def rtl_generation_node(state: WorkflowState) -> WorkflowState:
        checkpoint("generate_rtl:start")
        interface_contract = state.get("interface_contract", "")
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            rtl_code = sanitize_verilog_rtl(build_multiplier_rtl(multiplier_contract))
        elif config.dry_run:
            rtl_code = sanitize_verilog_rtl(_dry_rtl_code())
        else:
            system_prompt = prompt_library.build_rtl_system_prompt()
            user_prompt = (
                prompt_library.format("rtl_generation", specification=state["specification"])
                + build_rtl_generation_guidance(interface_contract)
            )
            rtl_code = sanitize_verilog_rtl(
                extract_verilog_code(
                    llm.invoke_text(
                        system_prompt,
                        user_prompt,
                        operation_label="generate_rtl:llm",
                    )
                )
            )
        updates = {"rtl_code": rtl_code}
        checkpoint("generate_rtl:complete", updates)
        return updates

    def tb_generation_node(state: WorkflowState) -> WorkflowState:
        checkpoint("generate_tb:start")
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            testbench_code = build_multiplier_testbench(multiplier_contract)
        elif config.dry_run:
            testbench_code = _dry_testbench_code()
        else:
            system_prompt = prompt_library.build_stage_system_prompt(
                stage="tb_generation",
                role_instruction="You generate deterministic self-checking Verilog testbenches for FPGA RTL.",
            )
            user_prompt = (
                prompt_library.format(
                    "tb_generation",
                    specification=state["specification"],
                    rtl_code=state["rtl_code"],
                )
                + build_tb_generation_guidance()
            )
            testbench_code = extract_verilog_code(
                llm.invoke_text(
                    system_prompt,
                    user_prompt,
                    operation_label="generate_tb:llm",
                )
            )
        updates = {"testbench_code": testbench_code}
        checkpoint("generate_tb:complete", updates)
        return updates

    def eda_checks_node(state: WorkflowState) -> WorkflowState:
        checkpoint("run_eda_checks:start")
        rtl_code = sanitize_verilog_rtl(state["rtl_code"])
        testbench_code = sanitize_verilog_testbench(state["testbench_code"])
        interface_contract = state.get("interface_contract", "")
        eda_result = run_prechecked_eda(
            run_dir=Path(state["run_dir"]),
            repo_root=config.repo_root,
            rtl_code=rtl_code,
            testbench_code=testbench_code,
            interface_contract=interface_contract,
            cancellation_check=cancellation_check,
        )
        updates = {"rtl_code": rtl_code, "testbench_code": testbench_code, "eda_result": eda_result}
        checkpoint("run_eda_checks:complete", updates)
        return updates

    def repair_node(state: WorkflowState) -> WorkflowState:
        checkpoint("repair_outputs:start")
        repair_attempts = state.get("repair_attempts", 0) + 1
        if config.dry_run or llm is None:
            updates = {"repair_attempts": repair_attempts}
            checkpoint("repair_outputs:complete", updates)
            return updates

        system_prompt = prompt_library.build_stage_system_prompt(
            stage="repair",
            role_instruction="You repair FPGA-oriented Verilog RTL and testbenches using the provided logs and constraints.",
        )
        eda_result = state["eda_result"]
        sim_log = eda_result.get("simulation_log", "")
        yosys_log = eda_result.get("yosys_log", "")
        interface_contract = state.get("interface_contract", "")
        interface_contract_failed = bool(eda_result.get("interface_contract_failed"))
        missing_module_definitions = list(eda_result.get("missing_module_definitions") or [])
        simulation_self_check_failed = bool(eda_result.get("simulation_self_check_failed"))
        testbench_only_failure = (
            eda_result.get("testbench_precheck_failed")
            or (
                "tb_candidate.v" in sim_log
                and "syntax error" in sim_log.lower()
                and eda_result.get("synthesis_passed")
            )
        )
        semantic_control_failure = (
            eda_result.get("synthesis_passed")
            and simulation_self_check_failed
        )
        repair_constraints = build_repair_constraints(
            interface_contract=interface_contract,
            interface_contract_failed=interface_contract_failed,
            missing_module_definitions=missing_module_definitions,
            testbench_only_failure=testbench_only_failure,
            semantic_control_failure=semantic_control_failure,
        )

        user_prompt = (
            prompt_library.format(
                "simulation_repair",
                specification=state["specification"],
                rtl_code=state["rtl_code"],
                tb_code=state["testbench_code"],
                sim_log=sim_log,
                yosys_log=yosys_log,
            )
            + repair_constraints
            + "\n\nDo not include illustrative or partial code blocks in the analysis. "
            + "Sections other than the final revised code must be prose only. "
            + "Return the revised RTL in the first complete ```verilog``` block and the revised testbench in a second complete ```verilog``` block only if the testbench must change."
        )
        repair_response = llm.invoke_text(
            system_prompt,
            user_prompt,
            operation_label="repair_outputs:llm",
        )
        repair_history = list(state.get("repair_history") or [])
        repair_history.append(
            {
                "attempt": repair_attempts,
                "label": f"Repair Attempt {repair_attempts}",
                "summary": (
                    "Focused on testbench repair."
                    if testbench_only_failure
                    else "Focused on local semantic control-path repair."
                    if semantic_control_failure
                    else "Focused on general repair and precheck convergence."
                ),
                "source": "workflow",
            }
        )
        if testbench_only_failure:
            repair_blocks = extract_code_blocks(
                repair_response,
                preferred_languages=("verilog", "systemverilog", "sv"),
            )
            rtl_code = state["rtl_code"]
            testbench_code = state["testbench_code"]
            if len(repair_blocks) >= 2:
                testbench_code = repair_blocks[1]
            elif len(repair_blocks) == 1 and "tb" in repair_blocks[0].lower():
                testbench_code = repair_blocks[0]
        else:
            rtl_code, repaired_testbench_code = extract_repair_artifacts(
                repair_response, state["testbench_code"]
            )

            header_guard_source = interface_contract or state["rtl_code"]
            original_top_module = infer_top_module_name(header_guard_source)
            repaired_top_module = infer_top_module_name(rtl_code)
            original_header = normalize_module_header(
                extract_module_header(header_guard_source, original_top_module) or ""
            )
            repaired_header = normalize_module_header(
                extract_module_header(rtl_code, repaired_top_module or original_top_module) or ""
            )

            if original_top_module and repaired_top_module != original_top_module:
                rtl_code = state["rtl_code"]
            elif original_header and repaired_header and repaired_header != original_header:
                rtl_code = state["rtl_code"]

            if semantic_control_failure:
                testbench_code = state["testbench_code"]
            else:
                testbench_code = repaired_testbench_code
        rtl_code = sanitize_verilog_rtl(rtl_code)
        testbench_code = sanitize_verilog_testbench(testbench_code)
        updates = {
            "rtl_code": rtl_code,
            "testbench_code": testbench_code,
            "repair_attempts": repair_attempts,
            "repair_response": repair_response,
            "repair_history": repair_history,
        }
        checkpoint("repair_outputs:complete", updates)
        return updates

    def review_node(state: WorkflowState) -> WorkflowState:
        checkpoint("review_outputs:start")
        multiplier_contract = detect_multiplier_contract(state["request"])
        if multiplier_contract is not None:
            artifact = build_multiplier_review(
                multiplier_contract,
                passed=bool(state.get("eda_result", {}).get("overall_pass")),
            )
        elif config.dry_run:
            artifact = _dry_review(state)
        else:
            system_prompt = prompt_library.build_stage_system_prompt(
                stage="review",
                role_instruction=(
                    "You are a hardware design reviewer. Evaluate whether the current outputs are coherent, "
                    "implementable, and ready for simulation and synthesis follow-up. Output only the schema requested."
                ),
            )
            user_prompt = dedent(
                f"""
                Review the current single-FPGA MVP outputs.

                Original task:
                {state['request']}

                Requirement analysis:
                {json.dumps(state['requirement_analysis'], ensure_ascii=False, indent=2)}

                Architecture design:
                {json.dumps(state['architecture_design'], ensure_ascii=False, indent=2)}

                Specification:
                {state['specification']}

                RTL:
                {state['rtl_code']}

                Testbench:
                {state['testbench_code']}

                EDA summary:
                {json.dumps(_eda_summary_for_review(state.get('eda_result', {})), ensure_ascii=False, indent=2)}

                Simulation log tail:
                {tail_text(state.get('eda_result', {}).get('simulation_log', ''), max_chars=3000)}

                Yosys log tail:
                {tail_text(state.get('eda_result', {}).get('yosys_log', ''), max_chars=3000)}
                """
            ).strip()
            artifact = llm.invoke_structured(
                system_prompt,
                user_prompt,
                StructuredStageOutput,
                operation_label="review_outputs:llm",
            )
        updates = {"review": artifact.model_dump()}
        checkpoint("review_outputs:complete", updates)
        return updates

    def route_after_eda(state: WorkflowState) -> str:
        eda_result = state.get("eda_result", {})
        if eda_result.get("missing_tools"):
            return "review"
        if eda_result.get("overall_pass"):
            return "review"
        if state.get("repair_attempts", 0) < 3:
            return "repair"
        return "review"

    graph.add_node("analyze_requirement", requirement_analysis_node)
    graph.add_node("design_architecture", architecture_design_node)
    graph.add_node("generate_spec", spec_generation_node)
    graph.add_node("generate_rtl", rtl_generation_node)
    graph.add_node("generate_tb", tb_generation_node)
    graph.add_node("run_eda_checks", eda_checks_node)
    graph.add_node("repair_outputs", repair_node)
    graph.add_node("review_outputs", review_node)

    graph.add_edge(START, "analyze_requirement")
    graph.add_edge("analyze_requirement", "design_architecture")
    graph.add_edge("design_architecture", "generate_spec")
    graph.add_edge("generate_spec", "generate_rtl")
    graph.add_edge("generate_rtl", "generate_tb")
    graph.add_edge("generate_tb", "run_eda_checks")
    graph.add_conditional_edges(
        "run_eda_checks",
        route_after_eda,
        {
            "repair": "repair_outputs",
            "review": "review_outputs",
        },
    )
    graph.add_edge("repair_outputs", "run_eda_checks")
    graph.add_edge("review_outputs", END)

    return graph.compile()


def _compose_spec_input(state: WorkflowState) -> str:
    return dedent(
        f"""
        Original task:
        {state['request']}

        Requirement analysis:
        {json.dumps(state['requirement_analysis'], ensure_ascii=False, indent=2)}

        Architecture design:
        {json.dumps(state['architecture_design'], ensure_ascii=False, indent=2)}
        """
    ).strip()


def _dry_requirement_analysis(request: str) -> StructuredStageOutput:
    return StructuredStageOutput(
        task_summary=_first_sentence(request),
        inputs=[
            "赛题原文与目标平台信息",
            "接口与性能约束",
            "已有提示词与参考资料",
        ],
        outputs=[
            "结构化需求分析",
            "架构设计输入",
            "后续 RTL/TB 生成约束",
        ],
        constraints=[
            "单 FPGA 模式",
            "LangGraph 工作流实现",
            "调用外部 API 而不是自训练模型",
            "中间结果必须结构化输出",
        ],
        performance_targets=[
            "MVP 可端到端运行",
            "后续易于接入仿真与综合闭环",
        ],
        technical_risks=[
            "赛题是系统级协处理器需求，直接映射到 RTL 时粒度过大",
            "SPI/UART、侧信道防护与算法内核的边界需要进一步收敛",
            "单 FPGA MVP 与后续 PSoC 模式存在接口抽象差异",
        ],
        questions_to_clarify=[
            "MVP 是否先只覆盖封装路径而不是三条全流程",
            "统一控制接口第一版优先 SPI 还是 UART",
            "是否允许先用行为上正确、结构上可扩展的骨架替代完整算法数据通路",
        ],
    )


def _dry_architecture_design(request: str, requirement_analysis: dict) -> StructuredStageOutput:
    return StructuredStageOutput(
        task_summary="构建单 FPGA 数字 IC Agent 的第一版 LangGraph 工作流，并能面向硬件任务生成规格、RTL 与 TB 草案。",
        inputs=[
            "原始赛题描述",
            "结构化需求分析结果",
            "project_prompt 下的 FPGA/RTL/TB 提示词",
        ],
        outputs=[
            "工作流节点编排",
            "规格说明文本",
            "RTL 与 Testbench 输出",
            "最终审查结果",
        ],
        constraints=[
            "只实现 fpga 模式",
            "每个阶段职责清晰，避免自由发散式 agent 对话",
            "先做 CLI MVP，不先做 UI",
        ],
        performance_targets=[
            "节点输出稳定落盘",
            "可在 dry-run 下无外部依赖完成流程验证",
            "真实 API 模式只需补环境变量即可使用",
        ],
        technical_risks=[
            "规格生成与 RTL 生成之间仍可能存在语义漂移",
            "未接入仿真器前，review 只能做静态审查",
            "复杂协处理器会超出首版 RTL 提示词的稳定边界",
        ],
        questions_to_clarify=[
            "后续是否把 simulation_repair 纳入默认图中形成闭环",
            "是否需要在 phase2 就加入开源仿真工具调用",
            "是否需要同时生成报告文档初稿",
        ],
    )


def _dry_specification(spec_input: str) -> str:
    return dedent(
        f"""
        1. Module goal
        Build a single-FPGA MVP control shell for a future HQC accelerator flow, with clear staging for command decode, control sequencing, and result reporting.

        2. Input/output ports proposal
        - clk, input, 1, system clock
        - rst_n, input, 1, active-low reset
        - cmd_valid, input, 1, command valid strobe
        - cmd_type, input, 2, operation selector
        - start, input, 1, start pulse
        - busy, output, 1, operation in progress
        - done, output, 1, operation finished pulse
        - status_code, output, 4, status reporting

        3. Clock/reset assumptions
        - Single clock domain
        - Active-low synchronous reset inside sequential logic

        4. Functional behavior
        - Capture a command when cmd_valid and start are asserted.
        - Raise busy during processing.
        - After a fixed latency, assert done for one cycle and update status_code.

        5. Timing behavior
        - Outputs update on the rising edge of clk.
        - The MVP uses a fixed multi-cycle placeholder latency for operation completion.

        6. Corner cases / boundary conditions
        - Ignore new start pulses while busy is high.
        - Reset returns the controller to idle deterministically.
        - Unsupported command types map to a non-zero status code.

        7. Explicit assumptions made due to ambiguity
        - This MVP models the control shell only, not the full HQC datapath.
        - A fixed latency placeholder is used to keep the RTL FPGA-friendly and testable.

        8. Items that should be confirmed by the user
        - Which operation should be prioritized first in silicon-oriented refinement.
        - Whether SPI or UART becomes the first integrated command ingress.

        9. Recommended implementation style
        - Sequential control with a small FSM and counter.

        Source context:
        {spec_input}
        """
    ).strip()


def _dry_rtl_code() -> str:
    return dedent(
        """
        module hqc_mvp_ctrl (
            input  wire       clk,
            input  wire       rst_n,
            input  wire       cmd_valid,
            input  wire [1:0] cmd_type,
            input  wire       start,
            output reg        busy,
            output reg        done,
            output reg  [3:0] status_code
        );

            localparam [1:0] ST_IDLE = 2'd0;
            localparam [1:0] ST_RUN  = 2'd1;
            localparam [1:0] ST_DONE = 2'd2;

            reg [1:0] state;
            reg [2:0] cycle_count;
            reg [1:0] latched_cmd_type;

            always @(posedge clk) begin
                if (!rst_n) begin
                    state <= ST_IDLE;
                    cycle_count <= 3'd0;
                    latched_cmd_type <= 2'd0;
                    busy <= 1'b0;
                    done <= 1'b0;
                    status_code <= 4'd0;
                end else begin
                    done <= 1'b0;

                    case (state)
                        ST_IDLE: begin
                            busy <= 1'b0;
                            cycle_count <= 3'd0;
                            if (cmd_valid && start) begin
                                state <= ST_RUN;
                                busy <= 1'b1;
                                latched_cmd_type <= cmd_type;
                                status_code <= 4'd0;
                            end
                        end

                        ST_RUN: begin
                            busy <= 1'b1;
                            cycle_count <= cycle_count + 3'd1;
                            if (cycle_count == 3'd4) begin
                                state <= ST_DONE;
                                busy <= 1'b0;
                                status_code <= {2'b00, latched_cmd_type};
                            end
                        end

                        ST_DONE: begin
                            state <= ST_IDLE;
                            done <= 1'b1;
                        end

                        default: begin
                            state <= ST_IDLE;
                            busy <= 1'b0;
                            done <= 1'b0;
                            status_code <= 4'hf;
                        end
                    endcase
                end
            end

        endmodule
        """
    ).strip()


def _dry_testbench_code() -> str:
    return dedent(
        """
        `timescale 1ns/1ps

        module tb_hqc_mvp_ctrl;
            reg clk;
            reg rst_n;
            reg cmd_valid;
            reg [1:0] cmd_type;
            reg start;
            wire busy;
            wire done;
            wire [3:0] status_code;

            integer error_count;

            hqc_mvp_ctrl dut (
                .clk(clk),
                .rst_n(rst_n),
                .cmd_valid(cmd_valid),
                .cmd_type(cmd_type),
                .start(start),
                .busy(busy),
                .done(done),
                .status_code(status_code)
            );

            always #5 clk = ~clk;

            initial begin
                clk = 1'b0;
                rst_n = 1'b0;
                cmd_valid = 1'b0;
                cmd_type = 2'b00;
                start = 1'b0;
                error_count = 0;

                repeat (3) @(posedge clk);
                @(negedge clk);
                rst_n = 1'b1;

                @(negedge clk);
                cmd_valid = 1'b1;
                cmd_type = 2'b10;
                start = 1'b1;

                @(negedge clk);
                cmd_valid = 1'b0;
                start = 1'b0;

                wait (done === 1'b1);
                if (status_code != 4'b0010) begin
                    $display("FAIL: unexpected status_code=%0d", status_code);
                    error_count = error_count + 1;
                end

                @(posedge clk);
                if (busy !== 1'b0) begin
                    $display("FAIL: busy should be low after completion");
                    error_count = error_count + 1;
                end

                if (error_count == 0) begin
                    $display("PASS: tb_hqc_mvp_ctrl completed without errors");
                end else begin
                    $display("FAIL: tb_hqc_mvp_ctrl found %0d errors", error_count);
                end

                $finish;
            end
        endmodule
        """
    ).strip()


def _dry_review(state: WorkflowState) -> StructuredStageOutput:
    eda_result = state.get("eda_result", {})
    tools_available = eda_result.get("tools_available", False)
    backend = eda_result.get("tool_backend", "none")
    overall_pass = eda_result.get("overall_pass", False)

    return StructuredStageOutput(
        task_summary=(
            "首版工作流已经覆盖从需求结构化到 RTL/TB 产出的主链路，"
            f"并已接入 EDA 后端（backend={backend}, tools_available={tools_available}, overall_pass={overall_pass}）；"
            "当前 RTL 仍是控制壳层示例，不是完整 HQC 算法实现。"
        ),
        inputs=[
            "需求分析结果",
            "架构设计结果",
            "规格说明",
            "RTL 与 Testbench 草案",
            "仿真与综合结果",
        ],
        outputs=[
            "可继续迭代的 MVP 评审结论",
            "后续仿真与综合关注点",
        ],
        constraints=[
            "当前只验证工作流，不验证真实后量子算法正确性",
            "当前样例仍是占位控制壳层，不代表完整算法核已经实现",
        ],
        performance_targets=[
            "保持仿真与综合闭环稳定运行",
            "把 simulation_repair 纳入自动反馈回路",
        ],
        technical_risks=[
            "复杂算法核心仍需更细粒度模块划分",
            "接口时序和缓存组织尚未映射到真实板级带宽预算",
            "安全机制目前仍停留在架构预留层面",
        ],
        questions_to_clarify=[
            "第一版是否只保留控制壳层与占位算法核",
            "是否把 UART/SPI 接口作为下一轮硬件实现重点",
            "是否立即接入开源仿真工具并自动解析日志",
        ],
    )


def _first_sentence(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "Empty task input"
    for separator in ("。", ". ", "\n"):
        if separator in normalized:
            return normalized.split(separator, maxsplit=1)[0].strip()
    return normalized[:120].strip()


def _eda_summary_for_review(eda_result: dict) -> dict:
    if not eda_result:
        return {}
    return {
        "tools_available": eda_result.get("tools_available"),
        "missing_tools": eda_result.get("missing_tools", []),
        "top_module": eda_result.get("top_module"),
        "simulation_passed": eda_result.get("simulation_passed"),
        "synthesis_passed": eda_result.get("synthesis_passed"),
        "overall_pass": eda_result.get("overall_pass"),
        "iverilog_returncode": eda_result.get("iverilog_returncode"),
        "simulation_returncode": eda_result.get("simulation_returncode"),
        "yosys_returncode": eda_result.get("yosys_returncode"),
    }
