from __future__ import annotations

from pathlib import Path
from typing import Callable

from .code_utils import (
    find_disconnected_direct_injection_signals,
    find_insufficient_sim_duration_issue,
    find_combinational_nonblocking_assignments,
    find_multiple_procedural_drivers,
    find_rtl_delay_controls,
    find_sequential_blocking_assignments,
    find_undriven_internal_wires,
    find_undefined_module_references,
    extract_module_header,
    infer_top_module_name,
    normalize_module_header,
)
from .eda import run_eda_checks


def load_interface_contract(task_file: Path | None) -> str:
    if task_file is None:
        return ""
    for candidate in (task_file.with_suffix(".interface.v"), task_file.with_suffix(".contract.v")):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


def validate_rtl_prechecks(rtl_code: str, interface_contract: str) -> tuple[list[str], bool, list[str]]:
    issues: list[str] = []
    interface_contract_failed = False

    if interface_contract:
        expected_top = infer_top_module_name(interface_contract)
        actual_top = infer_top_module_name(rtl_code)
        expected_header = normalize_module_header(
            extract_module_header(interface_contract, expected_top) or ""
        )
        actual_header = normalize_module_header(
            extract_module_header(rtl_code, actual_top or expected_top) or ""
        )
        if expected_top and actual_top != expected_top:
            interface_contract_failed = True
            issues.append(
                f"Interface contract mismatch: expected top module '{expected_top}', got '{actual_top or 'unknown'}'."
            )
        elif expected_header and actual_header and actual_header != expected_header:
            interface_contract_failed = True
            issues.append("Interface contract mismatch: top-level module declaration does not match the required header.")

    missing_modules = find_undefined_module_references(rtl_code)
    if missing_modules:
        issues.append(
            "RTL is not self-contained. Undefined instantiated modules: "
            + ", ".join(missing_modules)
            + "."
        )

    undriven_internal_wires = find_undriven_internal_wires(rtl_code)
    if undriven_internal_wires:
        issues.append(
            "RTL has undriven internal wire connections: "
            + ", ".join(undriven_internal_wires)
            + ". Each listed wire is declared locally and consumed as a submodule input, but no same-file driver was found."
        )

    delay_controls = find_rtl_delay_controls(rtl_code)
    if delay_controls:
        issues.append(
            "RTL uses delay controls (#), which are simulation-only and not acceptable in synthesizable RTL: "
            + "; ".join(delay_controls[:3])
            + "."
        )

    sequential_blocking_assignments = find_sequential_blocking_assignments(rtl_code)
    if sequential_blocking_assignments:
        issues.append(
            "RTL uses blocking assignments in edge-sensitive always blocks: "
            + ", ".join(sequential_blocking_assignments)
            + ". Use nonblocking assignments for sequential logic."
        )

    combinational_nonblocking_assignments = find_combinational_nonblocking_assignments(rtl_code)
    if combinational_nonblocking_assignments:
        issues.append(
            "RTL uses nonblocking assignments in combinational always blocks: "
            + ", ".join(combinational_nonblocking_assignments)
            + ". Use blocking assignments and provide full combinational defaults."
        )

    multiple_procedural_drivers = find_multiple_procedural_drivers(rtl_code)
    if multiple_procedural_drivers:
        issues.append(
            "RTL appears to drive the same procedural target from multiple always blocks: "
            + ", ".join(multiple_procedural_drivers)
            + ". Consolidate each register into a single owner process."
        )

    return issues, interface_contract_failed, missing_modules


def validate_testbench_prechecks(testbench_code: str, rtl_code: str) -> list[str]:
    issues: list[str] = []
    rtl_top = infer_top_module_name(rtl_code)
    tb_top = infer_top_module_name(testbench_code)

    if not tb_top:
        return ["Testbench precheck failed: no testbench module declaration was detected."]
    if rtl_top and tb_top == rtl_top:
        return [
            f"Testbench precheck failed: the testbench redefines DUT module '{rtl_top}' instead of declaring a separate *_tb module."
        ]

    disconnected_direct_injection_signals = find_disconnected_direct_injection_signals(
        testbench_code,
        rtl_code,
    )
    if disconnected_direct_injection_signals:
        issues.append(
            "Testbench precheck failed: detected disconnected direct-command stimulus signals "
            + ", ".join(disconnected_direct_injection_signals)
            + ". They are toggled locally but are neither DUT ports nor DUT instance connections, and no SPI/UART stimulus was found. Drive commands through the exposed SPI/UART interface instead."
        )

    insufficient_sim_duration_issue = find_insufficient_sim_duration_issue(testbench_code, rtl_code)
    if insufficient_sim_duration_issue:
        issues.append(insufficient_sim_duration_issue)

    return issues


def make_precheck_failure_result(
    *,
    run_dir: Path,
    rtl_code: str,
    testbench_code: str,
    issues: list[str],
    interface_contract_failed: bool,
    missing_module_definitions: list[str],
    testbench_precheck_failed: bool,
    tool_backend: str = "precheck",
) -> dict:
    eda_dir = run_dir / "eda"
    failure_log = "[precheck]\n" + "\n".join(issues)
    return {
        "eda_dir": str(eda_dir),
        "execution_dir": "",
        "rtl_path": str(eda_dir / "rtl_candidate.v"),
        "tb_path": str(eda_dir / "tb_candidate.v"),
        "tool_backend": tool_backend,
        "tool_paths": {},
        "missing_tools": [],
        "tools_available": True,
        "top_module": infer_top_module_name(rtl_code),
        "iverilog_returncode": 1,
        "simulation_returncode": 1,
        "yosys_returncode": 1,
        "simulation_log": failure_log,
        "yosys_log": failure_log,
        "simulation_passed": False,
        "simulation_self_check_failed": False,
        "synthesis_passed": False,
        "overall_pass": False,
        "interface_contract_failed": interface_contract_failed,
        "missing_module_definitions": missing_module_definitions,
        "testbench_precheck_failed": testbench_precheck_failed,
        "precheck_issues": issues,
        "rtl_path_exists": bool(rtl_code),
        "tb_path_exists": bool(testbench_code),
    }


def run_prechecked_eda(
    *,
    run_dir: Path,
    repo_root: Path,
    rtl_code: str,
    testbench_code: str,
    interface_contract: str,
    cancellation_check: Callable[[str], None] | None = None,
) -> dict:
    if cancellation_check is not None:
        cancellation_check("eda_precheck:start")
    precheck_issues, interface_contract_failed, missing_module_definitions = validate_rtl_prechecks(
        rtl_code,
        interface_contract,
    )
    testbench_precheck_issues = validate_testbench_prechecks(testbench_code, rtl_code)
    if testbench_precheck_issues:
        precheck_issues.extend(testbench_precheck_issues)
    if precheck_issues:
        return make_precheck_failure_result(
            run_dir=run_dir,
            rtl_code=rtl_code,
            testbench_code=testbench_code,
            issues=precheck_issues,
            interface_contract_failed=interface_contract_failed,
            missing_module_definitions=missing_module_definitions,
            testbench_precheck_failed=bool(testbench_precheck_issues),
        )
    if cancellation_check is not None:
        cancellation_check("eda_precheck:complete")
    return run_eda_checks(
        run_dir=run_dir,
        repo_root=repo_root,
        rtl_code=rtl_code,
        testbench_code=testbench_code,
        cancellation_check=cancellation_check,
    )


def build_interface_contract_check_result(
    *,
    run_dir: Path,
    rtl_code: str,
    interface_contract: str,
) -> dict:
    issues, interface_contract_failed, missing_module_definitions = validate_rtl_prechecks(
        rtl_code,
        interface_contract,
    )
    result = make_precheck_failure_result(
        run_dir=run_dir,
        rtl_code=rtl_code,
        testbench_code="",
        issues=issues or ["Interface contract check passed."],
        interface_contract_failed=interface_contract_failed,
        missing_module_definitions=missing_module_definitions,
        testbench_precheck_failed=False,
        tool_backend="interface_contract_check",
    )
    result["overall_pass"] = not bool(issues)
    result["simulation_passed"] = not bool(issues)
    result["synthesis_passed"] = not bool(issues)
    result["simulation_returncode"] = 0 if not issues else 1
    result["yosys_returncode"] = 0 if not issues else 1
    result["iverilog_returncode"] = 0 if not issues else 1
    result["simulation_log"] = "[contract-check]\n" + "\n".join(issues or ["Interface contract check passed."])
    result["yosys_log"] = result["simulation_log"]
    result["precheck_issues"] = issues
    return result
