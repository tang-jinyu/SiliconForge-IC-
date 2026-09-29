from __future__ import annotations

from dataclasses import dataclass
import re

from .models import StructuredStageOutput


MULTIPLIER_RE = re.compile(r"(?P<a>\d+)\s*[x×*]\s*(?P<b>\d+)\s*[^\n]{0,24}?乘法器", re.IGNORECASE)


@dataclass(frozen=True)
class MultiplierContract:
    a_width: int
    b_width: int
    signed: bool = False

    @property
    def product_width(self) -> int:
        return self.a_width + self.b_width

    @property
    def module_name(self) -> str:
        prefix = "smult" if self.signed else "mult"
        return f"{prefix}{self.a_width}x{self.b_width}"


def detect_multiplier_contract(request: str) -> MultiplierContract | None:
    match = MULTIPLIER_RE.search(request)
    if match is None:
        return None
    a_width = int(match.group("a"))
    b_width = int(match.group("b"))
    if not (1 <= a_width <= 4096 and 1 <= b_width <= 4096):
        return None
    signed = bool(re.search(r"有符号|signed", request, re.IGNORECASE))
    return MultiplierContract(a_width=a_width, b_width=b_width, signed=signed)


def build_multiplier_analysis(contract: MultiplierContract) -> StructuredStageOutput:
    kind = "signed" if contract.signed else "unsigned"
    return StructuredStageOutput(
        task_summary=f"Pure combinational {contract.a_width}x{contract.b_width} {kind} multiplier",
        inputs=[f"a[{contract.a_width - 1}:0]", f"b[{contract.b_width - 1}:0]"],
        outputs=[f"p[{contract.product_width - 1}:0] full-precision product"],
        constraints=["No clock or reset", "Verilog-2001", "Icarus/Vivado simulation and Yosys synthesis"],
        performance_targets=["Exact full-width arithmetic", "Zero cycle latency"],
        technical_risks=["FPGA resource use and combinational timing depend on target DSP architecture"],
        questions_to_clarify=[],
    )


def build_multiplier_architecture(contract: MultiplierContract) -> StructuredStageOutput:
    return StructuredStageOutput(
        task_summary="Minimal contract-frozen arithmetic datapath",
        inputs=["Frozen two-operand interface"],
        outputs=["One self-contained multiplier module", "Independent deterministic self-checking testbench"],
        constraints=["No protocol or handshake injection", "No result truncation"],
        performance_targets=["Simulation PASS", "Synthesis PASS"],
        technical_risks=["Large widths may map to several DSP blocks or LUT fabric"],
        questions_to_clarify=[],
    )


def build_multiplier_spec(contract: MultiplierContract) -> str:
    signedness = "signed two's-complement" if contract.signed else "unsigned"
    port_signed = " signed" if contract.signed else ""
    return f"""# Frozen RTL Specification

## Task classification

Purely combinational arithmetic datapath.

## Module goal

Compute the exact {signedness} product `p = a * b` with no truncation.

## Frozen top-level interface

```verilog
module {contract.module_name} (
    input wire{port_signed} [{contract.a_width - 1}:0] a,
    input wire{port_signed} [{contract.b_width - 1}:0] b,
    output wire{port_signed} [{contract.product_width - 1}:0] p
);
```

No other ports exist. There is no clock, reset, valid, ready, or transport interface.

## Behavior and timing

- `p` is the full {contract.product_width}-bit product of `a` and `b`.
- The circuit is combinational and has no cycle latency or stored state.
- Output changes after ordinary combinational propagation delay.

## Verification contract

The testbench shall check zero, one, maximum operands, alternating patterns, power-of-two cases, operand symmetry, and at least 20 deterministic generated vectors. Expected results use {contract.product_width}-bit operands and result storage. Exactly one final `TEST_PASS` or `TEST_FAIL` marker determines success.

## Synthesis contract

Verilog-2001; no latches, sequential elements, delays, or external modules. The multiplier may infer FPGA DSP and/or LUT resources. Vivado-compatible ANSI ports must carry explicit net types under `default_nettype none`.

## Assumptions

The short requirement does not request pipelining or signed arithmetic beyond the signedness selected above, so the smallest conventional combinational interface is used.
"""


def build_multiplier_rtl(contract: MultiplierContract) -> str:
    signed_kw = " signed" if contract.signed else ""
    return f"""`default_nettype none
module {contract.module_name} (
    input wire{signed_kw} [{contract.a_width - 1}:0] a,
    input wire{signed_kw} [{contract.b_width - 1}:0] b,
    output wire{signed_kw} [{contract.product_width - 1}:0] p
);
    assign p = a * b;
endmodule
`default_nettype wire
"""


def build_multiplier_testbench(contract: MultiplierContract) -> str:
    signed_kw = " signed" if contract.signed else ""
    a_extension_bit = "a[AW-1]" if contract.signed else "1'b0"
    b_extension_bit = "b[BW-1]" if contract.signed else "1'b0"
    a_extend_expr = "{{(PW-AW){" + a_extension_bit + "}}, a}"
    b_extend_expr = "{{(PW-BW){" + b_extension_bit + "}}, b}"
    return f"""`timescale 1ns/1ps
`default_nettype none
module tb_{contract.module_name};
    localparam integer AW = {contract.a_width};
    localparam integer BW = {contract.b_width};
    localparam integer PW = {contract.product_width};

    reg{signed_kw} [AW-1:0] a;
    reg{signed_kw} [BW-1:0] b;
    wire{signed_kw} [PW-1:0] p;
    reg{signed_kw} [PW-1:0] expected;
    reg{signed_kw} [PW-1:0] a_ext;
    reg{signed_kw} [PW-1:0] b_ext;
    integer failures;
    integer i;

    {contract.module_name} dut (.a(a), .b(b), .p(p));

    task check_product;
        begin
            a_ext = {a_extend_expr};
            b_ext = {b_extend_expr};
            expected = a_ext * b_ext;
            #1;
            if (p !== expected) begin
                failures = failures + 1;
                $display("FAIL a=%h b=%h expected=%h got=%h", a, b, expected, p);
            end
        end
    endtask

    initial begin
        failures = 0;
        a = {{AW{{1'b0}}}}; b = {{BW{{1'b0}}}}; check_product;
        a = {{{{(AW-1){{1'b0}}}}, 1'b1}}; b = {{{{(BW-1){{1'b0}}}}, 1'b1}}; check_product;
        a = {{AW{{1'b1}}}}; b = {{BW{{1'b1}}}}; check_product;
        a = {{AW{{1'b1}}}}; b = {{{{(BW-1){{1'b0}}}}, 1'b1}}; check_product;
        a = {{AW{{1'b0}}}}; b = {{BW{{1'b1}}}}; check_product;
        a = {{AW{{1'b1}}}}; b = {{BW{{1'b0}}}}; check_product;
        a = {{AW{{1'b1}}}}; b = {{BW{{1'b0}}}}; b[0] = 1'b1; check_product;
        for (i = 0; i < 32; i = i + 1) begin
            a = i * 32'h1f123bb5;
            b = (i + 3) * 32'h9e3779b9;
            check_product;
        end
        if (failures == 0)
            $display("TEST_PASS");
        else
            $display("TEST_FAIL failures=%0d", failures);
        $finish;
    end
endmodule
`default_nettype wire
"""


def build_multiplier_review(contract: MultiplierContract, passed: bool) -> StructuredStageOutput:
    return StructuredStageOutput(
        task_summary=f"{contract.a_width}x{contract.b_width} multiplier delivery review",
        inputs=["Frozen specification", "RTL", "self-checking testbench", "EDA evidence"],
        outputs=["Delivery is closed-loop ready" if passed else "Delivery requires repair"],
        constraints=["Exact interface preserved", "Full-width product preserved"],
        performance_targets=["Simulation and synthesis both pass"],
        technical_risks=[] if passed else ["EDA quality gate did not pass"],
        questions_to_clarify=[],
    )
