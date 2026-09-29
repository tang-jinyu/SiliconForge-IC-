from __future__ import annotations

from textwrap import dedent


HELPER_MODULE_CATEGORY_TEXT = (
    "protocol adapters, scratch or key memories, FIFOs, crypto cores, or arithmetic accelerators"
)
TESTBENCH_VISIBLE_SIGNAL_TEXT = (
    "uart_tx, spi_miso, cmd_ready, cmd_busy, result_valid, resp_valid, result_data, resp_data, "
    "fault_detect, and side_chain_mon"
)


def build_expert_rtl_quality_skill() -> str:
    return dedent(
        """

        Expert hardware-quality skill:
        - Make clock, reset polarity, and reset release behavior explicit. Keep one dominant clock domain unless the task explicitly requires CDC logic.
        - Give each stateful register and each contract-visible status/result register a single owning procedural block.
        - Use nonblocking assignments in edge-sensitive always blocks and blocking assignments in combinational always blocks with explicit default assignments.
        - Keep externally visible completion, busy, valid, error, and result signals observable long enough for a downstream controller or testbench to sample them deterministically.
        - Size arithmetic, concatenation, and comparison paths explicitly. Preserve carry bits and signedness intentionally instead of relying on implicit width extension.
        - Prefer clock-enable style data gating over gated clocks. Avoid combinational feedback, internal tri-states, and simulation-only constructs.
        - Use inference-friendly counters, RAMs, and FSMs. If helper logic is small, inline it; if it is instantiated, include the full same-file synthesizable definition.
        - During repair, preserve the top-level contract and fix the smallest local control or datapath root cause rather than rewriting the architecture.
        """
    )


def build_rtl_generation_guidance(interface_contract: str) -> str:
    guidance = dedent(
        f"""

        Return the complete RTL in a single ```verilog``` code block.
        Return self-contained RTL only: every non-primitive instantiated module must have its full synthesizable definition in the same code block.
        Do not leave {HELPER_MODULE_CATEGORY_TEXT} undefined.
        If helper behavior is local and simple, inline it or include a same-file synthesizable implementation instead of relying on external dependencies.
        {build_expert_rtl_quality_skill().strip()}
        """
    )
    if not interface_contract:
        return guidance

    return (
        guidance
        + dedent(
            f"""

            Top-level interface contract (must match exactly):
            ```verilog
            {interface_contract.strip()}
            ```
            Keep the exact top-level module name and module port declaration above.
            Do not procedurally assign directly to output wire ports declared in the contract; drive internal regs and connect them with continuous assign statements instead.
            """
        )
    )


def build_tb_generation_guidance() -> str:
    return dedent(
        """

        Use strict Verilog-2001 syntax compatible with Icarus Verilog.
        Do not use SystemVerilog-only array literals such as '{default:...}', and avoid constructs that require unpacked literal arguments.
        Return only a separate self-checking testbench module.
        Do not restate or redefine the DUT RTL, and never reuse the DUT top module name as the testbench module name.
        Drive commands through the declared external ingress path, such as SPI or UART, rather than inventing shortcut signals.
        Keep checks on testbench-visible outputs and externally observable handshakes instead of hidden internal DUT state.
        Return the complete testbench in a single ```verilog``` code block.
        """
    )


def build_repair_constraints(
    *,
    interface_contract: str,
    interface_contract_failed: bool,
    missing_module_definitions: list[str],
    testbench_only_failure: bool,
    semantic_control_failure: bool,
) -> str:
    constraints = dedent(
        f"""

        Icarus Verilog compatibility requirements: use strict Verilog-2001 only.
        Do not use SystemVerilog-only syntax such as declarations inside for-loop headers, declarations inside procedural blocks after statements, unpacked array task arguments, or return statements inside tasks.
        Keep the revised RTL self-contained for the provided test flow: do not introduce new instantiated modules unless their full synthesizable definitions are included in the revised RTL code block.
        Do not leave {HELPER_MODULE_CATEGORY_TEXT} undefined; if one is missing, add the minimal same-file helper implementation or inline equivalent local logic without changing the top-level interface.
        Do not procedurally assign directly to top-level output wire ports; use internal regs plus continuous assigns.
        The testbench must never drive DUT output-only ports such as {TESTBENCH_VISIBLE_SIGNAL_TEXT}.
        {build_expert_rtl_quality_skill().strip()}
        """
    )

    if interface_contract_failed and interface_contract:
        constraints += dedent(
            f"""
            The current RTL violates the required top-level interface contract before EDA.
            Restore the exact top-level module name and module declaration below before changing internals.
            Required top-level contract:
            ```verilog
            {interface_contract.strip()}
            ```
            """
        )

    if missing_module_definitions:
        constraints += (
            " The current RTL is not self-contained. Undefined instantiated modules: "
            + ", ".join(missing_module_definitions)
            + ". Eliminate every listed undefined module by name in the returned RTL. Do not leave placeholder instantiations, black boxes, comments, or prose-only descriptions. Either inline their full synthesizable definitions in the same RTL block or replace each instantiation with equivalent local logic without changing the top-level interface, the top-level controller architecture, or testbench-visible behavior."
        )

    if testbench_only_failure:
        constraints += (
            " Keep the RTL functionally unchanged unless the simulation log proves the RTL is the cause. "
            "The synthesis pass already succeeded, so focus on fixing the testbench syntax and event ordering. "
            "Return the original RTL as the first ```verilog``` block and a complete revised testbench as the second ```verilog``` block."
        )
    elif semantic_control_failure:
        constraints += (
            " Synthesis already passes, so prioritize RTL semantic repair over architectural rewrites. "
            "Trace the command path from external input sampling through command-valid generation, opcode decode, start handshake, main FSM transition, and finally busy, done, and error outputs. "
            "If the controller remains in IDLE or busy never asserts, identify the first signal in that chain that fails and fix that root cause directly. "
            "Preserve the top-level module name, ports, external protocol behavior, and testbench-visible outputs unless the logs prove a direct contradiction. "
            "Match the provided testbench handshake semantics exactly and limit fixes to local control logic such as command capture, opcode latch timing, state transition conditions, busy or done generation, valid pulse hold behavior, and counter reset behavior."
        )

    return constraints
