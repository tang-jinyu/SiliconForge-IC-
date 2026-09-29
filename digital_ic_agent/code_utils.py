from __future__ import annotations

import re
from textwrap import dedent


CODE_BLOCK_RE = re.compile(r"```(?P<lang>[\w+-]*)\n(?P<code>.*?)```", re.DOTALL)
MODULE_RE = re.compile(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b")
MODULE_HEADER_RE = re.compile(r"\bmodule\b[\s\S]*?;\s*", re.DOTALL)
MODULE_DECL_RE = re.compile(
    r"(?s)\bmodule\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([\s\S]*?\)\s*)?\((?P<ports>[\s\S]*?)\)\s*;"
)
MODULE_BLOCK_RE = re.compile(
    r"(?s)\bmodule\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b[\s\S]*?\bendmodule\b"
)
TIMESCALE_RE = re.compile(r"(?m)^\s*`timescale\b.*$")
ENDMODULE_RE = re.compile(r"(?m)^\s*endmodule\b")
RTL_SECTION_RE = re.compile(
    r"(?ism)^\s*#+\s*(?:\d+\.\s*)?Revised RTL Code\b\s*(?P<section>.*?)(?=^\s*#+\s*(?:\d+\.\s*)?Revised Testbench Code\b|\Z)",
)
TESTBENCH_SECTION_RE = re.compile(
    r"(?ism)^\s*#+\s*(?:\d+\.\s*)?Revised Testbench Code\b\s*(?P<section>.*)$",
)
TASK_BLOCK_RE = re.compile(
    r"(?P<header>\btask\b(?:\s+automatic)?\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*;\s*)(?P<body>.*?)(?P<footer>\bendtask\b)",
    re.DOTALL,
)
RETURN_STATEMENT_RE = re.compile(r"\breturn\s*;")
TASK_INPUT_BYTE_ARRAY_DECL_RE = re.compile(
    r"(?m)^\s*input\s+\[7:0\]\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s+\[0:\d+\]\s*;\s*$"
)
TASK_OUTPUT_BYTE_ARRAY_DECL_RE = re.compile(
    r"(?m)^\s*output\s+\[7:0\]\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s+\[0:\d+\]\s*;\s*$"
)
ZEROED_BYTE_ARRAY_LITERAL_RE = re.compile(r"'\{\s*default\s*:\s*8'h00\s*\}")
ZERO_PAYLOAD_COMMAND_CALL_RE = re.compile(
    r"(?P<prefix>\b(?:spi|uart)_send_command\s*\(\s*[^,]+,\s*[^,]+)\s*,\s*(?:'\{\s*default\s*:\s*8'h00\s*\}|tb_zero_payload|tb_payload_bytes)\s*,\s*(?P<data_len>[^)]+)\)"
)
SPI_COMMAND_ARRAY_CALL_RE = re.compile(
    r"(?P<indent>^\s*)spi_send_command\s*\(\s*(?P<cmd>[^,]+),\s*(?P<payload>[A-Za-z_][A-Za-z0-9_$]*)\s*,\s*(?P<payload_len>[^)]+)\);\s*$",
    re.MULTILINE,
)
SPI_COMMAND_AND_RECEIVE_ARRAY_CALL_RE = re.compile(
    r"(?P<indent>^\s*)spi_send_command_and_receive\s*\(\s*(?P<cmd>[^,]+),\s*(?P<payload>[A-Za-z_][A-Za-z0-9_$]*)\s*,\s*(?P<payload_len>[^,]+),\s*(?P<response>[A-Za-z_][A-Za-z0-9_$]*)\s*,\s*(?P<response_len>[^)]+)\);\s*$",
    re.MULTILINE,
)
FOR_LOOP_INDEX_RE = re.compile(r"\bfor\s*\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*=")
MODULE_INSTANTIATION_RE = re.compile(
    r"(?m)^\s*(?!module\b|endmodule\b|if\b|else\b|for\b|while\b|case\b|casex\b|casez\b|assign\b|always\b|initial\b|begin\b|end\b|wire\b|reg\b|logic\b|input\b|output\b|inout\b|parameter\b|localparam\b|function\b|task\b|generate\b|endgenerate\b)(?P<module>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([\s\S]*?\)\s*)?(?P<instance>[A-Za-z_][A-Za-z0-9_$]*)\s*\(",
)
MODULE_INSTANTIATION_BLOCK_RE = re.compile(
    r"(?ms)^\s*(?!module\b|endmodule\b|if\b|else\b|for\b|while\b|case\b|casex\b|casez\b|assign\b|always\b|initial\b|begin\b|end\b|wire\b|reg\b|logic\b|input\b|output\b|inout\b|parameter\b|localparam\b|function\b|task\b|generate\b|endgenerate\b)(?P<module>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([\s\S]*?\)\s*)?(?P<instance>[A-Za-z_][A-Za-z0-9_$]*)\s*\((?P<connections>[\s\S]*?)\)\s*;"
)
ALWAYS_START_RE = re.compile(r"(?m)^\s*always\b")
ALWAYS_HEADER_RE = re.compile(r"\balways\s*@\s*(?P<sensitivity>\*|\([^)]*\))")
PROCEDURAL_ASSIGNMENT_RE = re.compile(
    r"(?m)^\s*(?P<target>[A-Za-z_][A-Za-z0-9_$]*)(?:\[[^\]]+\])?\s*(?P<operator><=|=(?!=))"
)
NAMED_PORT_CONNECTION_RE = re.compile(
    r"\.\s*(?P<port>[A-Za-z_][A-Za-z0-9_$]*)\s*\(\s*(?P<signal>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:\[[^\]]+\])?\s*\)"
)
PORT_DIRECTION_RE = re.compile(
    r"\b(?P<direction>input|output|inout)\b(?:\s+(?:reg|wire|logic|signed|unsigned))*\s*(?:\[[^\]]+\]\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b"
)
WIRE_DECL_RE = re.compile(r"(?m)^\s*wire\b(?P<declarators>[^;]+);")
ASSIGN_TARGET_RE = re.compile(
    r"(?m)^\s*assign\s+(?P<target>[A-Za-z_][A-Za-z0-9_$]*)\s*(?:\[[^\]]+\])?\s*="
)
DIRECT_INJECTION_DECL_RE = re.compile(
    r"(?m)^\s*(?:reg|wire|logic)\b[^;]*\b(?P<name>test_cmd|test_cmd_valid|cmd_data|cmd_valid)\b[^;]*;"
)
COMMAND_STIMULUS_CALL_RE = re.compile(
    r"(?m)^\s*(?:spi_send_command(?:_and_receive)?|uart_send_command(?:_and_receive)?|send_command)\s*\("
)
DIRECT_VALID_ASSERT_RE = re.compile(
    r"(?m)^\s*(?:test_cmd_valid|cmd_valid)\s*(?:<=|=)\s*(?:1'b1|1'h1|1)\s*;"
)
RESULT_WAIT_RE = re.compile(r"\bwait\s*\(\s*(?:result_valid|resp_valid)\s*\)")
PARAM_ASSIGNMENT_RE = re.compile(
    r"(?m)^\s*(?:parameter|localparam)\b[^;]*\b(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b\s*=\s*(?P<value>[^;]+);"
)
NUMERIC_LITERAL_RE = re.compile(r"\b(?:\d+'[dDhHbBoO][0-9a-fA-F_xXzZ]+|\d[\d_]*)\b")

DEFAULT_OPERATION_CYCLE_BUDGET = 600
OPERATION_INTERFACE_OVERHEAD_CYCLES = 40
TESTBENCH_SETUP_CYCLES = 20

VERILOG_PRIMITIVES = {
    "and",
    "buf",
    "bufif0",
    "bufif1",
    "cmos",
    "nand",
    "nmos",
    "nor",
    "notif0",
    "notif1",
    "or",
    "pmos",
    "pulldown",
    "pullup",
    "rcmos",
    "rnmos",
    "rpmos",
    "rtran",
    "rtranif0",
    "rtranif1",
    "tran",
    "tranif0",
    "tranif1",
    "xnor",
    "xor",
}

VERILOG_RESERVED_WORDS = {
    "begin",
    "case",
    "casex",
    "casez",
    "default",
    "else",
    "end",
    "endcase",
    "endfunction",
    "endgenerate",
    "endmodule",
    "endtask",
    "for",
    "function",
    "generate",
    "if",
    "initial",
    "module",
    "task",
    "while",
}

TESTBENCH_ARRAY_HELPER = dedent(
    """
    reg [7:0] tb_payload_bytes [0:131071];
    reg [7:0] tb_response_bytes [0:131071];
    integer tb_array_init_idx;
    integer tb_payload_copy_idx;
    integer tb_response_copy_idx;
    initial begin
        for (tb_array_init_idx = 0; tb_array_init_idx < 131072; tb_array_init_idx = tb_array_init_idx + 1) begin
            tb_payload_bytes[tb_array_init_idx] = 8'h00;
            tb_response_bytes[tb_array_init_idx] = 8'h00;
        end
    end
    """
).strip()

COMMON_DUT_OUTPUT_NAMES = {
    "cmd_ready",
    "cmd_busy",
    "result_valid",
    "resp_valid",
    "result_data",
    "resp_data",
    "fault_detect",
    "side_chain_mon",
    "spi_miso",
    "uart_tx",
}
COMMON_DUT_OUTPUT_REG_DECL_RE = re.compile(
    r"(?m)^(?P<indent>\s*)reg(?P<spacing>\s+)(?P<width>\[[^\]]+\]\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*;\s*$"
)
ANSI_PORT_WITHOUT_NET_TYPE_RE = re.compile(
    r"(?m)^(?P<indent>\s*)(?P<direction>input|output|inout)"
    r"(?![ \t]+(?:wire|reg|logic|tri|wand|wor|integer)\b)"
    r"(?P<spacing>[ \t]+)"
)
ANSI_DUPLICATE_WIRE_RE = re.compile(
    r"(?m)^(?P<prefix>\s*(?:input|output|inout)\s+)wire\s+wire\b"
)


def extract_code_blocks(text: str, preferred_languages: tuple[str, ...] = ()) -> list[str]:
    matches = list(CODE_BLOCK_RE.finditer(text))
    if not matches:
        return []

    normalized_languages = {language.lower() for language in preferred_languages}
    preferred_blocks = [
        match.group("code").strip()
        for match in matches
        if match.group("lang").lower() in normalized_languages
    ]
    if preferred_blocks:
        return preferred_blocks
    return [match.group("code").strip() for match in matches]


def extract_verilog_code(text: str) -> str:
    code_blocks = extract_code_blocks(text, preferred_languages=("verilog", "systemverilog", "sv"))
    if code_blocks:
        return code_blocks[0]
    recovered_region = _extract_verilog_region(text)
    if recovered_region:
        return recovered_region
    partial_region = _extract_partial_verilog_region(text)
    if partial_region:
        return partial_region
    return text.strip()


def sanitize_verilog_rtl(text: str) -> str:
    # Vivado 2018.3 rejects ANSI port declarations with an omitted net type
    # when `default_nettype none` is active, although Yosys accepts them.
    if "`default_nettype none" in text:
        text = ANSI_DUPLICATE_WIRE_RE.sub(lambda match: f"{match.group('prefix')}wire", text)
        text = ANSI_PORT_WITHOUT_NET_TYPE_RE.sub(
            lambda match: (
                f"{match.group('indent')}{match.group('direction')}"
                f"{match.group('spacing')}wire "
            ),
            text,
        )
    module_matches = list(MODULE_RE.finditer(text))
    if len(module_matches) == 1 and not ENDMODULE_RE.search(text, module_matches[0].start()):
        stripped = text.rstrip()
        return f"{stripped}\nendmodule\n"
    if len(module_matches) <= 1:
        return text

    endmodule_matches = list(ENDMODULE_RE.finditer(text))
    if len(endmodule_matches) >= len(module_matches):
        return text

    sanitized_parts: list[str] = []
    cursor = 0
    endmodule_index = 0

    for module_index, module_match in enumerate(module_matches):
        while (
            endmodule_index < len(endmodule_matches)
            and endmodule_matches[endmodule_index].start() < module_match.start()
        ):
            endmodule_index += 1

        if module_index > 0 and module_index > endmodule_index:
            segment = text[cursor: module_match.start()]
            sanitized_parts.append(segment)
            if segment and not segment.endswith("\n"):
                sanitized_parts.append("\n")
            sanitized_parts.append("endmodule\n\n")
            cursor = module_match.start()

    sanitized_parts.append(text[cursor:])
    sanitized = "".join(sanitized_parts)
    return sanitized if sanitized != text else text


def sanitize_verilog_testbench(text: str) -> str:
    sanitized = text
    changed = False
    helper_needed = False

    rewritten_outputs = COMMON_DUT_OUTPUT_REG_DECL_RE.sub(
        lambda match: (
            f"{match.group('indent')}wire{match.group('spacing')}{match.group('width') or ''}{match.group('name')};"
            if match.group("name") in COMMON_DUT_OUTPUT_NAMES
            else match.group(0)
        ),
        sanitized,
    )
    if rewritten_outputs != sanitized:
        sanitized = rewritten_outputs
        changed = True

    if ZERO_PAYLOAD_COMMAND_CALL_RE.search(sanitized):
        sanitized = ZERO_PAYLOAD_COMMAND_CALL_RE.sub(
            lambda match: f"{match.group('prefix')}, {match.group('data_len')})",
            sanitized,
        )
        changed = True

    if ZEROED_BYTE_ARRAY_LITERAL_RE.search(sanitized):
        sanitized = ZEROED_BYTE_ARRAY_LITERAL_RE.sub("tb_payload_bytes", sanitized)
        changed = True
        helper_needed = True

    if SPI_COMMAND_AND_RECEIVE_ARRAY_CALL_RE.search(sanitized):
        sanitized = SPI_COMMAND_AND_RECEIVE_ARRAY_CALL_RE.sub(
            lambda match: "\n".join(
                [
                    f"{match.group('indent')}for (tb_payload_copy_idx = 0; tb_payload_copy_idx < {match.group('payload_len').strip()}; tb_payload_copy_idx = tb_payload_copy_idx + 1) begin",
                    f"{match.group('indent')}    tb_payload_bytes[tb_payload_copy_idx] = {match.group('payload').strip()}[tb_payload_copy_idx];",
                    f"{match.group('indent')}end",
                    f"{match.group('indent')}spi_send_command_and_receive({match.group('cmd').strip()}, {match.group('payload_len').strip()}, {match.group('response_len').strip()});",
                    f"{match.group('indent')}for (tb_response_copy_idx = 0; tb_response_copy_idx < {match.group('response_len').strip()}; tb_response_copy_idx = tb_response_copy_idx + 1) begin",
                    f"{match.group('indent')}    {match.group('response').strip()}[tb_response_copy_idx] = tb_response_bytes[tb_response_copy_idx];",
                    f"{match.group('indent')}end",
                ]
            ),
            sanitized,
        )
        changed = True
        helper_needed = True

    if SPI_COMMAND_ARRAY_CALL_RE.search(sanitized):
        sanitized = SPI_COMMAND_ARRAY_CALL_RE.sub(
            lambda match: "\n".join(
                [
                    f"{match.group('indent')}for (tb_payload_copy_idx = 0; tb_payload_copy_idx < {match.group('payload_len').strip()}; tb_payload_copy_idx = tb_payload_copy_idx + 1) begin",
                    f"{match.group('indent')}    tb_payload_bytes[tb_payload_copy_idx] = {match.group('payload').strip()}[tb_payload_copy_idx];",
                    f"{match.group('indent')}end",
                    f"{match.group('indent')}spi_send_command({match.group('cmd').strip()}, {match.group('payload_len').strip()});",
                ]
            ),
            sanitized,
        )
        changed = True
        helper_needed = True

    task_return_replacements = 0
    task_array_rewrites = 0

    def rewrite_task_returns(match: re.Match[str]) -> str:
        nonlocal helper_needed, task_array_rewrites, task_return_replacements

        rewritten_body = match.group("body")

        while True:
            input_array_match = TASK_INPUT_BYTE_ARRAY_DECL_RE.search(rewritten_body)
            if not input_array_match:
                break
            rewritten_body = TASK_INPUT_BYTE_ARRAY_DECL_RE.sub("", rewritten_body, count=1)
            rewritten_body = re.sub(
                rf"\b{re.escape(input_array_match.group('name'))}\s*\[",
                "tb_payload_bytes[",
                rewritten_body,
            )
            helper_needed = True
            task_array_rewrites += 1

        while True:
            output_array_match = TASK_OUTPUT_BYTE_ARRAY_DECL_RE.search(rewritten_body)
            if not output_array_match:
                break
            rewritten_body = TASK_OUTPUT_BYTE_ARRAY_DECL_RE.sub("", rewritten_body, count=1)
            rewritten_body = re.sub(
                rf"\b{re.escape(output_array_match.group('name'))}\s*\[",
                "tb_response_bytes[",
                rewritten_body,
            )
            helper_needed = True
            task_array_rewrites += 1

        rewritten_body, replacements = RETURN_STATEMENT_RE.subn(
            f"disable {match.group('name')};",
            rewritten_body,
        )
        task_return_replacements += replacements
        return f"{match.group('header')}{rewritten_body}{match.group('footer')}"

    sanitized = TASK_BLOCK_RE.sub(rewrite_task_returns, sanitized)
    if task_array_rewrites or task_return_replacements:
        changed = True

    missing_loop_indices = _find_missing_loop_index_names(sanitized)
    if missing_loop_indices:
        changed = True

    if not changed:
        return text
    if not helper_needed and not missing_loop_indices:
        return sanitized

    module_header = MODULE_HEADER_RE.search(sanitized)
    if not module_header:
        return sanitized

    injected_blocks: list[str] = []
    if helper_needed and "reg [7:0] tb_payload_bytes [" not in sanitized:
        injected_blocks.append(TESTBENCH_ARRAY_HELPER)
    if missing_loop_indices:
        injected_blocks.append("\n".join(f"integer {name};" for name in missing_loop_indices))
    if not injected_blocks:
        return sanitized

    return (
        sanitized[: module_header.end()]
        + "\n"
        + "\n\n".join(injected_blocks)
        + "\n\n"
        + sanitized[module_header.end() :]
    )


def extract_repair_artifacts(text: str, current_tb_code: str) -> tuple[str, str]:
    code_blocks = extract_code_blocks(text, preferred_languages=("verilog", "systemverilog", "sv"))
    if not code_blocks:
        rtl_section = _extract_named_verilog_region(text, RTL_SECTION_RE) or _extract_verilog_region(text)
        tb_section = _extract_named_verilog_region(text, TESTBENCH_SECTION_RE)
        if rtl_section or tb_section:
            return rtl_section or text.strip(), tb_section or current_tb_code
        return text.strip(), current_tb_code

    module_blocks = [block for block in code_blocks if infer_top_module_name(block)]
    if not module_blocks:
        if len(code_blocks) == 1:
            return code_blocks[0], current_tb_code
        return code_blocks[0], code_blocks[1]

    current_tb_module = infer_top_module_name(current_tb_code)
    testbench_blocks = [
        block
        for block in module_blocks
        if _is_testbench_code_block(block, current_tb_module)
    ]
    rtl_blocks = [block for block in module_blocks if block not in testbench_blocks]

    rtl_code = max(rtl_blocks or module_blocks, key=len)

    if testbench_blocks:
        testbench_code = max(testbench_blocks, key=len)
    else:
        alternate_blocks = [block for block in module_blocks if block != rtl_code]
        testbench_code = max(alternate_blocks, key=len) if alternate_blocks else current_tb_code

    return rtl_code, testbench_code


def _is_testbench_code_block(block: str, current_tb_module: str | None) -> bool:
    module_name = infer_top_module_name(block)
    if module_name is None:
        return False
    if current_tb_module and module_name == current_tb_module:
        return True
    lowered_module_name = module_name.lower()
    if lowered_module_name.startswith("tb_") or lowered_module_name.endswith("_tb"):
        return True
    lowered_block = block.lower()
    return "$dumpfile" in lowered_block or "$finish" in lowered_block


def _extract_named_verilog_region(text: str, section_re: re.Pattern[str]) -> str | None:
    section_match = section_re.search(text)
    if not section_match:
        return None

    section_text = section_match.group("section").strip()
    if not section_text:
        return None

    code_blocks = extract_code_blocks(section_text, preferred_languages=("verilog", "systemverilog", "sv"))
    if code_blocks:
        return code_blocks[0]

    return _extract_verilog_region(section_text)


def _extract_verilog_region(text: str) -> str | None:
    module_match = MODULE_RE.search(text)
    if not module_match:
        return None

    endmodule_matches = list(ENDMODULE_RE.finditer(text, module_match.start()))
    if not endmodule_matches:
        return None

    timescale_match = None
    for candidate in TIMESCALE_RE.finditer(text):
        if candidate.start() < module_match.start():
            timescale_match = candidate
        else:
            break

    start = timescale_match.start() if timescale_match else module_match.start()
    end = endmodule_matches[-1].end()
    return text[start:end].strip()


def _extract_partial_verilog_region(text: str) -> str | None:
    module_match = MODULE_RE.search(text)
    timescale_match = TIMESCALE_RE.search(text)

    candidates = [
        match.start()
        for match in (timescale_match, module_match)
        if match is not None
    ]
    if not candidates:
        return None

    return text[min(candidates) :].strip()


def extract_module_header(verilog_text: str, module_name: str | None = None) -> str | None:
    for match in MODULE_DECL_RE.finditer(verilog_text):
        if module_name is None or match.group("name") == module_name:
            return match.group(0).strip()
    return None


def normalize_module_header(header: str) -> str:
    without_comments = re.sub(r"(?m)//.*$", "", header)
    collapsed_whitespace = re.sub(r"\s+", " ", without_comments)
    return collapsed_whitespace.strip()


def _find_missing_loop_index_names(verilog_text: str) -> list[str]:
    missing_names: list[str] = []
    seen_names: set[str] = set()

    for match in FOR_LOOP_INDEX_RE.finditer(verilog_text):
        name = match.group("name")
        if name in seen_names:
            continue
        seen_names.add(name)
        if _has_identifier_declaration(verilog_text, name):
            continue
        missing_names.append(name)

    return missing_names


def _has_identifier_declaration(verilog_text: str, name: str) -> bool:
    declaration_re = re.compile(
        rf"(?m)^\s*(?:integer|genvar|reg|wire|logic)\b[^;]*\b{re.escape(name)}\b[^;]*;"
    )
    return bool(declaration_re.search(verilog_text))


def find_undefined_module_references(verilog_text: str) -> list[str]:
    defined_modules = {match.group(1) for match in MODULE_RE.finditer(verilog_text)}
    referenced_modules: list[str] = []

    for match in MODULE_INSTANTIATION_RE.finditer(verilog_text):
        module_name = match.group("module")
        lowered_module_name = module_name.lower()
        if (
            module_name in defined_modules
            or lowered_module_name in VERILOG_PRIMITIVES
            or lowered_module_name in VERILOG_RESERVED_WORDS
        ):
            continue
        if module_name not in referenced_modules:
            referenced_modules.append(module_name)

    return referenced_modules


def find_undriven_internal_wires(verilog_text: str) -> list[str]:
    top_module_name = infer_top_module_name(verilog_text)
    if top_module_name is None:
        return []

    top_module_block = _find_module_block(verilog_text, top_module_name)
    if top_module_block is None:
        return []

    module_port_directions = _extract_module_port_directions(verilog_text)
    declared_wires = _extract_declared_wire_names(top_module_block)
    if not declared_wires:
        return []

    driven_signals = {match.group("target") for match in ASSIGN_TARGET_RE.finditer(top_module_block)}
    consumed_as_module_input: set[str] = set()

    for match in MODULE_INSTANTIATION_BLOCK_RE.finditer(top_module_block):
        module_name = match.group("module")
        port_directions = module_port_directions.get(module_name, {})
        if not port_directions:
            continue

        for connection_match in NAMED_PORT_CONNECTION_RE.finditer(match.group("connections")):
            signal_name = connection_match.group("signal")
            port_direction = port_directions.get(connection_match.group("port"))
            if port_direction in {"output", "inout"}:
                driven_signals.add(signal_name)
            elif port_direction == "input":
                consumed_as_module_input.add(signal_name)

    undriven_wires = [
        name
        for name in declared_wires
        if name not in driven_signals and name in consumed_as_module_input
    ]
    return undriven_wires


def find_sequential_blocking_assignments(verilog_text: str) -> list[str]:
    problematic_targets: list[str] = []

    for module_match in MODULE_BLOCK_RE.finditer(verilog_text):
        module_name = module_match.group("name")
        for always_block in _iter_always_blocks(module_match.group(0)):
            if not _is_edge_sensitive_always_block(always_block):
                continue
            for assignment_match in PROCEDURAL_ASSIGNMENT_RE.finditer(_strip_line_comments(always_block)):
                if assignment_match.group("operator") != "=":
                    continue
                scoped_name = f"{module_name}.{assignment_match.group('target')}"
                if scoped_name not in problematic_targets:
                    problematic_targets.append(scoped_name)

    return problematic_targets


def find_combinational_nonblocking_assignments(verilog_text: str) -> list[str]:
    problematic_targets: list[str] = []

    for module_match in MODULE_BLOCK_RE.finditer(verilog_text):
        module_name = module_match.group("name")
        for always_block in _iter_always_blocks(module_match.group(0)):
            if _is_edge_sensitive_always_block(always_block):
                continue
            for assignment_match in PROCEDURAL_ASSIGNMENT_RE.finditer(_strip_line_comments(always_block)):
                if assignment_match.group("operator") != "<=":
                    continue
                scoped_name = f"{module_name}.{assignment_match.group('target')}"
                if scoped_name not in problematic_targets:
                    problematic_targets.append(scoped_name)

    return problematic_targets


def find_multiple_procedural_drivers(verilog_text: str) -> list[str]:
    problematic_targets: list[str] = []

    for module_match in MODULE_BLOCK_RE.finditer(verilog_text):
        module_name = module_match.group("name")
        target_owners: dict[str, int] = {}
        for always_block in _iter_always_blocks(module_match.group(0)):
            block_targets = {
                assignment_match.group("target")
                for assignment_match in PROCEDURAL_ASSIGNMENT_RE.finditer(_strip_line_comments(always_block))
            }
            for target in block_targets:
                target_owners[target] = target_owners.get(target, 0) + 1

        for target, owner_count in target_owners.items():
            if owner_count < 2:
                continue
            scoped_name = f"{module_name}.{target}"
            if scoped_name not in problematic_targets:
                problematic_targets.append(scoped_name)

    return problematic_targets


def find_rtl_delay_controls(verilog_text: str) -> list[str]:
    offending_lines: list[str] = []

    for raw_line in verilog_text.splitlines():
        code_line = raw_line.split("//", 1)[0].strip()
        if not code_line:
            continue
        if code_line.startswith("#"):
            offending_lines.append(code_line)
        elif re.search(r"<=\s*#\s*(?:\(|\d|[A-Za-z_'])", code_line):
            offending_lines.append(code_line)
        elif re.search(r"(?<![<>=!])=\s*#\s*(?:\(|\d|[A-Za-z_'])", code_line):
            offending_lines.append(code_line)

    unique_lines: list[str] = []
    for line in offending_lines:
        if line not in unique_lines:
            unique_lines.append(line)
    return unique_lines


def find_disconnected_direct_injection_signals(testbench_code: str, rtl_code: str) -> list[str]:
    rtl_top = infer_top_module_name(rtl_code)
    if rtl_top is None:
        return []

    rtl_port_names = set(_extract_module_port_directions(rtl_code).get(rtl_top, {}))
    dut_connected_signals = _extract_dut_connected_signal_names(testbench_code, rtl_top)
    if not dut_connected_signals:
        return []

    suspicious_signals: list[str] = []
    for match in DIRECT_INJECTION_DECL_RE.finditer(testbench_code):
        signal_name = match.group("name")
        if signal_name in rtl_port_names or signal_name in dut_connected_signals:
            continue
        if _count_signal_assignments(testbench_code, signal_name) < 2:
            continue
        if signal_name not in suspicious_signals:
            suspicious_signals.append(signal_name)

    has_valid_signal = any(name.endswith("valid") for name in suspicious_signals)
    has_data_signal = any(name in {"test_cmd", "cmd_data"} for name in suspicious_signals)
    if not (has_valid_signal and has_data_signal):
        return []
    if _has_meaningful_interface_stimulus(testbench_code):
        return []
    return suspicious_signals


def find_insufficient_sim_duration_issue(testbench_code: str, rtl_code: str) -> str | None:
    clk_period = _extract_numeric_parameter_value(testbench_code, "CLK_PERIOD")
    sim_duration = _extract_numeric_parameter_value(testbench_code, "SIM_DURATION")
    operation_count = estimate_testbench_operation_count(testbench_code)

    if clk_period is None or sim_duration is None or operation_count <= 0:
        return None

    operation_cycle_budget = infer_operation_cycle_budget(rtl_code)
    estimated_min_duration = int(
        (TESTBENCH_SETUP_CYCLES + operation_count * (operation_cycle_budget + OPERATION_INTERFACE_OVERHEAD_CYCLES))
        * clk_period
    )
    if sim_duration >= estimated_min_duration:
        return None

    return (
        "Testbench precheck failed: SIM_DURATION="
        + str(sim_duration)
        + " is likely too short for roughly "
        + str(operation_count)
        + " command operations at CLK_PERIOD="
        + str(clk_period)
        + ". A rough minimum is about "
        + str(estimated_min_duration)
        + " based on the observed operation count and RTL latency budget. Increase SIM_DURATION so the full regression can complete with slack."
    )


def estimate_testbench_operation_count(testbench_code: str) -> int:
    stimulus_call_count = len(list(COMMAND_STIMULUS_CALL_RE.finditer(testbench_code)))
    direct_valid_pulse_count = len(list(DIRECT_VALID_ASSERT_RE.finditer(testbench_code)))
    result_wait_count = len(list(RESULT_WAIT_RE.finditer(testbench_code)))
    return max(stimulus_call_count + direct_valid_pulse_count, result_wait_count)


def infer_operation_cycle_budget(rtl_code: str) -> int:
    candidate_values: list[int] = []

    for line in rtl_code.splitlines():
        code_line = line.split("//", 1)[0]
        lowered_line = code_line.lower()
        if not any(token in lowered_line for token in ("counter", "cycle", "cycles", "latency", "timer")):
            continue
        for literal_match in NUMERIC_LITERAL_RE.finditer(code_line):
            literal_value = _parse_numeric_verilog_literal(literal_match.group(0))
            if literal_value is None:
                continue
            if 64 <= literal_value <= 1_000_000:
                candidate_values.append(literal_value)

    if candidate_values:
        return max(candidate_values)
    return DEFAULT_OPERATION_CYCLE_BUDGET


def infer_top_module_name(rtl_code: str) -> str | None:
    match = MODULE_RE.search(rtl_code)
    if not match:
        return None
    return match.group(1)


def _find_module_block(verilog_text: str, module_name: str) -> str | None:
    for match in MODULE_BLOCK_RE.finditer(verilog_text):
        if match.group("name") == module_name:
            return match.group(0)
    return None


def _iter_always_blocks(module_block: str) -> list[str]:
    starts = list(ALWAYS_START_RE.finditer(module_block))
    if not starts:
        return []

    blocks: list[str] = []
    for index, start_match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(module_block)
        blocks.append(module_block[start_match.start() : end])
    return blocks


def _is_edge_sensitive_always_block(always_block: str) -> bool:
    header_match = ALWAYS_HEADER_RE.search(always_block)
    if not header_match:
        return False
    sensitivity = header_match.group("sensitivity").lower()
    return "posedge" in sensitivity or "negedge" in sensitivity


def _strip_line_comments(text: str) -> str:
    return re.sub(r"(?m)//.*$", "", text)


def _extract_dut_connected_signal_names(testbench_code: str, module_name: str) -> set[str]:
    for match in MODULE_INSTANTIATION_BLOCK_RE.finditer(testbench_code):
        if match.group("module") != module_name:
            continue
        return {
            connection_match.group("signal")
            for connection_match in NAMED_PORT_CONNECTION_RE.finditer(match.group("connections"))
        }
    return set()


def _extract_module_port_directions(verilog_text: str) -> dict[str, dict[str, str]]:
    module_port_directions: dict[str, dict[str, str]] = {}

    for module_match in MODULE_DECL_RE.finditer(verilog_text):
        port_directions: dict[str, str] = {}
        for port_match in PORT_DIRECTION_RE.finditer(module_match.group("ports")):
            port_directions[port_match.group("name")] = port_match.group("direction")
        module_port_directions[module_match.group("name")] = port_directions

    return module_port_directions


def _extract_declared_wire_names(module_block: str) -> list[str]:
    wire_names: list[str] = []

    for match in WIRE_DECL_RE.finditer(module_block):
        declarators = re.sub(r"//.*$", "", match.group("declarators")).strip()
        declarators = re.sub(r"\[[^\]]+\]", " ", declarators)
        for part in declarators.split(","):
            stripped_part = part.strip()
            if not stripped_part:
                continue
            name_match = re.search(r"([A-Za-z_][A-Za-z0-9_$]*)\s*(?:=.*)?$", stripped_part)
            if not name_match:
                continue
            wire_name = name_match.group(1)
            if wire_name not in wire_names:
                wire_names.append(wire_name)

    return wire_names


def _count_signal_assignments(verilog_text: str, signal_name: str) -> int:
    assignment_re = re.compile(rf"(?m)(?<![A-Za-z0-9_$]){re.escape(signal_name)}\s*=")
    return len(list(assignment_re.finditer(verilog_text)))


def _extract_numeric_parameter_value(verilog_text: str, parameter_name: str) -> int | None:
    for match in PARAM_ASSIGNMENT_RE.finditer(verilog_text):
        if match.group("name") != parameter_name:
            continue
        return _parse_numeric_verilog_literal(match.group("value").strip())
    return None


def _parse_numeric_verilog_literal(raw_value: str) -> int | None:
    value = raw_value.strip().replace("_", "")
    if not value:
        return None
    if value.isdigit():
        return int(value)

    sized_literal_match = re.fullmatch(r"(?:\d+)?'(?P<base>[dDhHbBoO])(?P<digits>[0-9a-fA-FxXzZ]+)", value)
    if not sized_literal_match:
        return None

    digits = sized_literal_match.group("digits")
    if any(ch in digits for ch in "xXzZ"):
        return None

    base = sized_literal_match.group("base").lower()
    base_map = {"d": 10, "h": 16, "b": 2, "o": 8}
    return int(digits, base_map[base])


def _has_meaningful_interface_stimulus(testbench_code: str) -> bool:
    interface_stimulus_patterns = (
        r"\bspi_cs_n\s*=\s*(?:1'b0|1'h0|0)\b",
        r"\bspi_sclk\s*=\s*(?:1'b1|1'h1|1)\b",
        r"\buart_rx\s*=\s*(?:1'b0|1'h0|0)\b",
    )
    return any(re.search(pattern, testbench_code) for pattern in interface_stimulus_patterns)


def tail_text(text: str, max_chars: int = 4000) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[-max_chars:]
