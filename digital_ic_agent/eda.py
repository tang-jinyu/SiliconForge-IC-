from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import shutil
from pathlib import Path
from typing import Callable

from .code_utils import infer_top_module_name


SIMULATION_TIMEOUT_SECONDS = int(os.getenv("DIGITAL_IC_AGENT_SIM_TIMEOUT_SECONDS", "60"))
SYNTHESIS_TIMEOUT_SECONDS = int(os.getenv("DIGITAL_IC_AGENT_SYNTH_TIMEOUT_SECONDS", "180"))
SIMULATION_SELF_CHECK_FAILURE_RE = re.compile(r"(^|\n)\s*FAIL\s*:", re.IGNORECASE)
SIMULATION_ERROR_RE = re.compile(r"(^|\n)\s*ERROR\s*:", re.IGNORECASE)
SIMULATION_SUMMARY_FAILURE_RE = re.compile(r"\bSOME TESTS FAILED\b", re.IGNORECASE)


def run_eda_checks(
    run_dir: Path,
    repo_root: Path,
    rtl_code: str,
    testbench_code: str,
    cancellation_check: Callable[[str], None] | None = None,
) -> dict:
    if cancellation_check is not None:
        cancellation_check("eda:start")
    run_dir = run_dir.resolve()
    eda_dir = run_dir / "eda"
    eda_dir.mkdir(parents=True, exist_ok=True)

    rtl_path = eda_dir / "rtl_candidate.v"
    tb_path = eda_dir / "tb_candidate.v"
    sim_out_path = eda_dir / "simulation.out"
    yosys_script_path = eda_dir / "synth.ys"

    rtl_path.write_text(rtl_code, encoding="utf-8")
    tb_path.write_text(testbench_code, encoding="utf-8")

    tool_paths = {
        "iverilog": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_IVERILOG_BIN", "iverilog"),
        "vvp": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_VVP_BIN", "vvp"),
        "yosys": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_YOSYS_BIN", "yosys"),
    }
    missing_tools = [name for name, path in tool_paths.items() if path is None]
    top_module = infer_top_module_name(rtl_code)
    vivado_paths = {
        "xvlog": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_XVLOG_BIN", "xvlog"),
        "xelab": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_XELAB_BIN", "xelab"),
        "xsim": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_XSIM_BIN", "xsim"),
        "vivado": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_VIVADO_BIN", "vivado"),
        "yowasp_yosys": _resolve_yowasp_yosys_path(),
    }

    execution_dir = eda_dir
    exec_rtl_path = rtl_path
    exec_tb_path = tb_path
    exec_sim_out_path = sim_out_path
    exec_yosys_script_path = yosys_script_path
    native_env: dict[str, str] | None = None

    if tool_paths["iverilog"] is not None:
        suite_root = tool_paths["iverilog"].parent.parent
        native_env = os.environ.copy()
        native_env["YOSYSHQ_ROOT"] = str(suite_root) + os.sep
        native_env["PATH"] = os.pathsep.join(
            [str(suite_root / "bin"), str(suite_root / "lib"), native_env.get("PATH", "")]
        )

    native_backend = not missing_tools and _native_toolchain_healthy(tool_paths, native_env)
    vivado_backend = not native_backend and all(
        vivado_paths[name] for name in ("xvlog", "xelab", "xsim", "vivado")
    )
    # WSL is a final fallback. Probing it on every run can block on Windows
    # machines where WSL is installed but has not been initialized.
    wsl_backend = not native_backend and not vivado_backend and _wsl_tools_available()

    if vivado_backend:
        return _run_vivado_checks(
            eda_dir=eda_dir,
            rtl_path=rtl_path,
            tb_path=tb_path,
            rtl_code=rtl_code,
            testbench_code=testbench_code,
            top_module=top_module,
            tool_paths=vivado_paths,
            cancellation_check=cancellation_check,
        )

    if wsl_backend:
        missing_tools = []
    elif not native_backend:
        missing_tools = ["healthy iverilog/vvp/yosys, Vivado, or WSL EDA backend"]

    if wsl_backend:
        execution_dir = _prepare_wsl_execution_dir(run_dir.name, rtl_code, testbench_code)
        exec_rtl_path = execution_dir / rtl_path.name
        exec_tb_path = execution_dir / tb_path.name
        exec_sim_out_path = execution_dir / sim_out_path.name
        exec_yosys_script_path = execution_dir / yosys_script_path.name

    result = {
        "eda_dir": str(eda_dir),
        "execution_dir": str(execution_dir),
        "rtl_path": str(rtl_path),
        "tb_path": str(tb_path),
        "tool_backend": "wsl" if wsl_backend else "native",
        "tool_paths": {name: str(path) if path else None for name, path in tool_paths.items()},
        "missing_tools": missing_tools,
        "tools_available": not missing_tools,
        "top_module": top_module,
        "iverilog_returncode": None,
        "simulation_returncode": None,
        "yosys_returncode": None,
        "simulation_log": "",
        "yosys_log": "",
        "simulation_passed": False,
        "simulation_self_check_failed": False,
        "synthesis_passed": False,
        "overall_pass": False,
    }

    if missing_tools:
        result["simulation_log"] = "Missing required EDA tools: " + ", ".join(missing_tools)
        result["yosys_log"] = result["simulation_log"]
        return result

    if wsl_backend:
        compile_command = [
            "wsl",
            "-e",
            "bash",
            "-lc",
            " ".join(
                [
                    "iverilog",
                    "-g2012",
                    "-o",
                    _shell_quote(_to_wsl_path(exec_sim_out_path)),
                    _shell_quote(_to_wsl_path(exec_tb_path)),
                    _shell_quote(_to_wsl_path(exec_rtl_path)),
                ]
            ),
        ]
        compile_completed = _run_subprocess(
            compile_command,
            cwd=Path("C:/"),
            poll_check=(lambda: cancellation_check("eda:compile")) if cancellation_check else None,
        )
        result["tool_paths"] = {
            "iverilog": "wsl:iverilog",
            "vvp": "wsl:vvp",
            "yosys": "wsl:yosys",
        }
    else:
        compile_command = [
            str(tool_paths["iverilog"]),
            "-g2012",
            "-o",
            str(exec_sim_out_path),
            str(exec_tb_path),
            str(exec_rtl_path),
        ]
        compile_completed = _run_subprocess(
            compile_command,
            cwd=eda_dir,
            env=native_env,
            poll_check=(lambda: cancellation_check("eda:compile")) if cancellation_check else None,
        )

    result["iverilog_returncode"] = compile_completed.returncode
    compile_log = _merge_logs("iverilog", compile_completed)

    simulation_log = compile_log
    if compile_completed.returncode == 0:
        if cancellation_check is not None:
            cancellation_check("eda:compile:complete")
        if wsl_backend:
            simulation_command = [
                "wsl",
                "-e",
                "bash",
                "-lc",
                " && ".join(
                    [
                        f"cd {_shell_quote(_to_wsl_path(execution_dir))}",
                        " ".join(
                            [
                                "timeout",
                                f"{SIMULATION_TIMEOUT_SECONDS}s",
                                "vvp",
                                _shell_quote(exec_sim_out_path.name),
                            ]
                        ),
                    ]
                ),
            ]
            simulation_completed = _run_subprocess(
                simulation_command,
                cwd=Path("C:/"),
                poll_check=(lambda: cancellation_check("eda:simulate")) if cancellation_check else None,
            )
        else:
            simulation_command = [str(tool_paths["vvp"]), str(sim_out_path)]
            simulation_completed = _run_subprocess(
                simulation_command,
                cwd=eda_dir,
                env=native_env,
                timeout_seconds=SIMULATION_TIMEOUT_SECONDS,
                poll_check=(lambda: cancellation_check("eda:simulate")) if cancellation_check else None,
            )
        result["simulation_returncode"] = simulation_completed.returncode
        simulation_log = "\n\n".join(
            [
                compile_log,
                _merge_logs("vvp", simulation_completed),
            ]
        ).strip()
        result["simulation_self_check_failed"] = _simulation_log_has_self_check_failures(simulation_log)
        result["simulation_passed"] = (
            simulation_completed.returncode == 0 and not result["simulation_self_check_failed"]
        )
    else:
        result["simulation_returncode"] = compile_completed.returncode

    result["simulation_log"] = simulation_log

    if top_module is None:
        result["yosys_returncode"] = 1
        result["yosys_log"] = "Unable to infer top module name from generated RTL."
    else:
        exec_yosys_script_path.write_text(
            "\n".join(
                [
                    f"read_verilog {exec_rtl_path.name if not wsl_backend else _to_wsl_path(exec_rtl_path)}",
                    f"hierarchy -check -top {top_module}",
                    f"synth -top {top_module}",
                    "stat",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        if cancellation_check is not None:
            cancellation_check("eda:simulate:complete")
        if wsl_backend:
            yosys_command = [
                "wsl",
                "-e",
                "bash",
                "-lc",
                " ".join(
                    [
                        "yosys",
                        "-s",
                        _shell_quote(_to_wsl_path(exec_yosys_script_path)),
                    ]
                ),
            ]
            yosys_completed = _run_subprocess(
                yosys_command,
                cwd=Path("C:/"),
                poll_check=(lambda: cancellation_check("eda:synthesize")) if cancellation_check else None,
            )
        else:
            yosys_command = [str(tool_paths["yosys"]), "-s", str(exec_yosys_script_path)]
            yosys_completed = _run_subprocess(
                yosys_command,
                cwd=eda_dir,
                env=native_env,
                poll_check=(lambda: cancellation_check("eda:synthesize")) if cancellation_check else None,
            )
        result["yosys_returncode"] = yosys_completed.returncode
        result["yosys_log"] = _merge_logs("yosys", yosys_completed)
        result["synthesis_passed"] = yosys_completed.returncode == 0

    result["overall_pass"] = result["simulation_passed"] and result["synthesis_passed"]
    return result


def _simulation_log_has_self_check_failures(log: str) -> bool:
    return bool(
        SIMULATION_SELF_CHECK_FAILURE_RE.search(log)
        or SIMULATION_ERROR_RE.search(log)
        or SIMULATION_SUMMARY_FAILURE_RE.search(log)
    )


def _resolve_tool_path(repo_root: Path, env_var_name: str, binary_name: str) -> Path | None:
    env_value = os.getenv(env_var_name)
    if env_value:
        env_path = Path(env_value)
        if env_path.exists():
            return env_path

    platform_names = _platform_binary_names(binary_name)
    local_candidates = [
        root / name
        for root in (
            repo_root / "tools" / "oss-cad-suite" / "bin",
            repo_root / "tools" / "oss-cad-suite" / "oss-cad-suite" / "bin",
        )
        for name in platform_names
    ]
    for local_candidate in local_candidates:
        if local_candidate.exists():
            return local_candidate

    for name in platform_names:
        resolved = _find_on_path(name)
        if resolved is not None:
            return resolved
    return None


def _platform_binary_names(binary_name: str) -> tuple[str, ...]:
    stem = binary_name
    for suffix in (".exe", ".bat", ".cmd"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if os.name == "nt":
        return (f"{stem}.exe", f"{stem}.bat", f"{stem}.cmd", stem)
    return (stem,)


def _find_on_path(binary_name: str) -> Path | None:
    resolved = shutil.which(binary_name)
    return Path(resolved) if resolved else None


def _resolve_yowasp_yosys_path() -> Path | None:
    configured = os.getenv("DIGITAL_IC_AGENT_YOWASP_YOSYS_BIN")
    if configured and Path(configured).exists():
        return Path(configured)
    scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    names = ("yowasp-yosys.exe", "yowasp-yosys") if os.name == "nt" else ("yowasp-yosys",)
    for name in names:
        candidate = scripts_dir / name
        if candidate.exists():
            return candidate
        on_path = _find_on_path(name)
        if on_path is not None:
            return on_path
    return None


def _prepare_wsl_execution_dir(run_name: str, rtl_code: str, testbench_code: str) -> Path:
    temp_root = Path(tempfile.gettempdir()) / "digital_ic_agent_eda" / run_name
    temp_root.mkdir(parents=True, exist_ok=True)
    (temp_root / "rtl_candidate.v").write_text(rtl_code, encoding="utf-8")
    (temp_root / "tb_candidate.v").write_text(testbench_code, encoding="utf-8")
    return temp_root


def _wsl_tools_available() -> bool:
    if os.name != "nt":
        return False
    completed = _run_subprocess(
        ["wsl", "-e", "bash", "-lc", "command -v iverilog && command -v vvp && command -v yosys"],
        cwd=Path("C:/"),
        timeout_seconds=10,
    )
    return completed.returncode == 0


_NATIVE_HEALTH_CACHE: dict[str, bool] = {}


def _native_toolchain_healthy(tool_paths: dict[str, Path | None], env: dict[str, str] | None) -> bool:
    yosys_path = tool_paths.get("yosys")
    if yosys_path is None:
        return False
    cache_key = str(yosys_path.resolve())
    if cache_key not in _NATIVE_HEALTH_CACHE:
        completed = _run_subprocess(
            [str(yosys_path), "-V"],
            cwd=yosys_path.parent,
            timeout_seconds=15,
            env=env,
        )
        _NATIVE_HEALTH_CACHE[cache_key] = completed.returncode == 0
    return _NATIVE_HEALTH_CACHE[cache_key]


def _run_vivado_checks(
    *,
    eda_dir: Path,
    rtl_path: Path,
    tb_path: Path,
    rtl_code: str,
    testbench_code: str,
    top_module: str | None,
    tool_paths: dict[str, Path | None],
    cancellation_check: Callable[[str], None] | None,
) -> dict:
    tb_top = infer_top_module_name(testbench_code)
    # Vivado 2018.x can fail when its helper processes run from a mapped or
    # secondary drive. Execute in the Windows temp directory and keep the
    # canonical artifacts in the task output directory.
    execution_dir = Path(tempfile.mkdtemp(prefix="digital_ic_agent_vivado_"))
    exec_rtl_path = execution_dir / rtl_path.name
    exec_tb_path = execution_dir / tb_path.name
    exec_rtl_path.write_text(rtl_code, encoding="utf-8")
    exec_tb_path.write_text(testbench_code, encoding="utf-8")
    result = {
        "eda_dir": str(eda_dir),
        "execution_dir": str(execution_dir),
        "rtl_path": str(rtl_path),
        "tb_path": str(tb_path),
        "tool_backend": "vivado+yowasp-yosys" if tool_paths.get("yowasp_yosys") else "vivado",
        "tool_paths": {name: str(path) if path else None for name, path in tool_paths.items()},
        "missing_tools": [],
        "tools_available": True,
        "top_module": top_module,
        "iverilog_returncode": None,
        "simulation_returncode": None,
        "yosys_returncode": None,
        "simulation_log": "",
        "yosys_log": "",
        "simulation_passed": False,
        "simulation_self_check_failed": False,
        "synthesis_passed": False,
        "overall_pass": False,
    }
    if top_module is None or tb_top is None:
        result["simulation_log"] = "Unable to infer RTL or testbench top module."
        result["yosys_log"] = result["simulation_log"]
        return result

    compile_completed = _run_subprocess(
        [str(tool_paths["xvlog"]), "--sv", str(exec_tb_path), str(exec_rtl_path)],
        cwd=execution_dir,
        timeout_seconds=SIMULATION_TIMEOUT_SECONDS,
        poll_check=(lambda: cancellation_check("eda:compile")) if cancellation_check else None,
    )
    result["iverilog_returncode"] = compile_completed.returncode
    simulation_parts = [_merge_logs("xvlog", compile_completed)]
    simulation_returncode = compile_completed.returncode

    if compile_completed.returncode == 0:
        elaborate_completed = _run_subprocess(
            [str(tool_paths["xelab"]), tb_top, "-s", "digital_ic_agent_sim"],
            cwd=execution_dir,
            timeout_seconds=SIMULATION_TIMEOUT_SECONDS,
            poll_check=(lambda: cancellation_check("eda:elaborate")) if cancellation_check else None,
        )
        simulation_parts.append(_merge_logs("xelab", elaborate_completed))
        simulation_returncode = elaborate_completed.returncode
        if elaborate_completed.returncode == 0:
            simulate_completed = _run_subprocess(
                [str(tool_paths["xsim"]), "digital_ic_agent_sim", "-R"],
                cwd=execution_dir,
                timeout_seconds=SIMULATION_TIMEOUT_SECONDS,
                poll_check=(lambda: cancellation_check("eda:simulate")) if cancellation_check else None,
            )
            simulation_parts.append(_merge_logs("xsim", simulate_completed))
            simulation_returncode = simulate_completed.returncode

    simulation_log = "\n\n".join(simulation_parts)
    result["simulation_returncode"] = simulation_returncode
    result["simulation_log"] = simulation_log
    result["simulation_self_check_failed"] = _simulation_log_has_self_check_failures(simulation_log)
    result["simulation_passed"] = simulation_returncode == 0 and not result["simulation_self_check_failed"]

    if cancellation_check is not None:
        cancellation_check("eda:synthesize:start")
    if tool_paths.get("yowasp_yosys") is not None:
        synth_script = execution_dir / "synth_yosys.ys"
        synth_script.write_text(
            "\n".join(
                [
                    f"read_verilog {exec_rtl_path.name}",
                    f"hierarchy -check -top {top_module}",
                    f"synth -top {top_module}",
                    "stat",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        synth_completed = _run_subprocess(
            [str(tool_paths["yowasp_yosys"]), "-s", synth_script.name],
            cwd=execution_dir,
            timeout_seconds=SYNTHESIS_TIMEOUT_SECONDS,
            poll_check=(lambda: cancellation_check("eda:synthesize")) if cancellation_check else None,
        )
        synthesis_passed = synth_completed.returncode == 0
        synth_tool_name = "yowasp-yosys"
    else:
        synth_script = execution_dir / "synth_vivado.tcl"
        synth_script.write_text(
            "\n".join(
                [
                    f"read_verilog {{{exec_rtl_path.as_posix()}}}",
                    f"set synth_status [catch {{synth_design -top {top_module} -part xc7a35tcpg236-1}} synth_message]",
                    "puts $synth_message",
                    "if {$synth_status != 0} { puts {DIGITAL_IC_AGENT_SYNTH_FAIL}; exit 1 }",
                    "puts {DIGITAL_IC_AGENT_SYNTH_PASS}",
                    "exit",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        synth_completed = _run_subprocess(
            [
                str(tool_paths["vivado"]),
                "-mode",
                "batch",
                "-source",
                str(synth_script),
                "-nolog",
                "-nojournal",
            ],
            cwd=execution_dir,
            timeout_seconds=SYNTHESIS_TIMEOUT_SECONDS,
            poll_check=(lambda: cancellation_check("eda:synthesize")) if cancellation_check else None,
        )
        synthesis_passed = (
            "DIGITAL_IC_AGENT_SYNTH_PASS" in synth_completed.stdout
            and "DIGITAL_IC_AGENT_SYNTH_FAIL" not in synth_completed.stdout
        )
        synth_tool_name = "vivado"
    result["yosys_returncode"] = synth_completed.returncode
    result["yosys_log"] = _merge_logs(synth_tool_name, synth_completed)
    result["synthesis_passed"] = synthesis_passed
    result["overall_pass"] = result["simulation_passed"] and result["synthesis_passed"]
    return result


def _to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    suffix = str(resolved).replace("\\", "/")
    suffix = suffix[len(resolved.drive) :]
    return f"/mnt/{drive}{suffix}"


def _shell_quote(text: str) -> str:
    escaped = text.replace("'", "'\"'\"'")
    return f"'{escaped}'"


def _run_subprocess(
    command: list[str],
    cwd: Path,
    timeout_seconds: int | None = None,
    poll_check: Callable[[], None] | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
        )
        try:
            while True:
                returncode = process.poll()
                if returncode is not None:
                    process.communicate()
                    return subprocess.CompletedProcess(
                        command,
                        returncode,
                        stdout=_read_subprocess_output(stdout_file),
                        stderr=_read_subprocess_output(stderr_file),
                    )

                if poll_check is not None:
                    poll_check()

                if deadline is not None and time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    stdout = _read_subprocess_output(stdout_file)
                    stderr = _read_subprocess_output(stderr_file).strip()
                    timeout_message = f"Process timed out after {timeout_seconds} seconds."
                    if stderr:
                        stderr = f"{stderr}\n{timeout_message}"
                    else:
                        stderr = timeout_message
                    return subprocess.CompletedProcess(
                        command,
                        124,
                        stdout=stdout,
                        stderr=stderr,
                    )

                time.sleep(0.2)
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.communicate()
            raise


def _read_subprocess_output(file_obj) -> str:
    file_obj.seek(0)
    return file_obj.read().decode("utf-8", errors="replace")


def _merge_logs(tool_name: str, completed: subprocess.CompletedProcess[str]) -> str:
    output_parts = [f"[{tool_name}] returncode={completed.returncode}"]
    if completed.stdout:
        output_parts.append("[stdout]\n" + completed.stdout.strip())
    if completed.stderr:
        output_parts.append("[stderr]\n" + completed.stderr.strip())
    return "\n\n".join(output_parts).strip()
