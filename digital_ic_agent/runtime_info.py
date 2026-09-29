from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from .eda import _resolve_tool_path


def build_runtime_report(repo_root: Path) -> dict:
    """Return a public, secret-free runtime and portability report."""
    eda_tools = {
        "iverilog": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_IVERILOG_BIN", "iverilog"),
        "vvp": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_VVP_BIN", "vvp"),
        "yosys": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_YOSYS_BIN", "yosys"),
        "vivado": _resolve_tool_path(repo_root, "DIGITAL_IC_AGENT_VIVADO_BIN", "vivado"),
    }
    gpu = _read_nvidia_gpu()
    base_url = os.getenv("DIGITAL_IC_AGENT_BASE_URL", "").strip()
    profile = os.getenv("DIGITAL_IC_AGENT_ENV_PROFILE", "stepfun-local" if (repo_root / ".env.stepfun").exists() else "environment")
    model = os.getenv("DIGITAL_IC_AGENT_MODEL", "gpt-4.1")
    server_ready = all(eda_tools[name] is not None for name in ("iverilog", "vvp", "yosys"))
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "model": {
            "profile": profile,
            "name": model,
            "endpoint": _safe_endpoint(base_url),
            "transport": os.getenv("DIGITAL_IC_AGENT_LLM_TRANSPORT", "auto"),
            "configured": bool(os.getenv("DIGITAL_IC_AGENT_API_KEY")),
        },
        "gpu": gpu,
        "eda": {
            "ready": server_ready,
            "tools": {name: str(path) if path else None for name, path in eda_tools.items()},
        },
        "portability": {
            "containerized": Path("/.dockerenv").exists(),
            "server_ready": server_ready,
            "project_root": str(repo_root),
            "queue_root": str(repo_root / ".agent_queue"),
            "runs_root": str(repo_root / "runs"),
        },
    }


def _safe_endpoint(value: str) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        return "configured"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.hostname}{port}{path}"


def _read_nvidia_gpu() -> dict:
    command = shutil.which("nvidia-smi")
    if command is None:
        return {"available": False, "devices": [], "driver_version": None}
    try:
        completed = subprocess.run(
            [
                command,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "devices": [], "driver_version": None}
    if completed.returncode != 0:
        return {"available": False, "devices": [], "driver_version": None}
    devices = []
    driver_version = None
    for index, line in enumerate(completed.stdout.splitlines()):
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 3:
            continue
        driver_version = driver_version or fields[2]
        try:
            memory_mib = int(fields[1])
        except ValueError:
            memory_mib = None
        devices.append({"index": index, "name": fields[0], "memory_mib": memory_mib})
    return {"available": bool(devices), "devices": devices, "driver_version": driver_version}
