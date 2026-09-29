from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from .environment import load_project_environment


@dataclass(frozen=True)
class AppConfig:
    model: str
    api_key: str | None
    base_url: str | None
    temperature: float
    mode: str
    dry_run: bool
    repo_root: Path
    llm_timeout_seconds: float
    llm_transport: str
    llm_max_attempts: int = 2
    llm_retry_backoff_seconds: float = 1.5
    llm_fallback_model: str | None = None

    @classmethod
    def from_env(
        cls,
        mode: str = "fpga",
        dry_run: bool = False,
        *,
        repo_root: Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> "AppConfig":
        load_project_environment()
        repo_root = repo_root or Path(__file__).resolve().parents[1]
        overrides = overrides or {}
        return cls(
            model=str(overrides.get("model") or os.getenv("DIGITAL_IC_AGENT_MODEL", "gpt-4.1")),
            api_key=_coalesce_optional_str(overrides.get("api_key"), os.getenv("DIGITAL_IC_AGENT_API_KEY")),
            base_url=_coalesce_optional_str(overrides.get("base_url"), os.getenv("DIGITAL_IC_AGENT_BASE_URL")),
            temperature=float(overrides.get("temperature", os.getenv("DIGITAL_IC_AGENT_TEMPERATURE", "0"))),
            mode=mode,
            dry_run=dry_run,
            repo_root=repo_root,
            llm_timeout_seconds=float(overrides.get("llm_timeout_seconds", os.getenv("DIGITAL_IC_AGENT_LLM_TIMEOUT_SECONDS", "300"))),
            llm_transport=str(overrides.get("llm_transport") or os.getenv("DIGITAL_IC_AGENT_LLM_TRANSPORT", "auto")),
            llm_max_attempts=int(overrides.get("llm_max_attempts", os.getenv("DIGITAL_IC_AGENT_LLM_MAX_ATTEMPTS", "2"))),
            llm_retry_backoff_seconds=float(overrides.get("llm_retry_backoff_seconds", os.getenv("DIGITAL_IC_AGENT_LLM_RETRY_BACKOFF_SECONDS", "1.5"))),
            llm_fallback_model=_coalesce_optional_str(overrides.get("llm_fallback_model"), os.getenv("DIGITAL_IC_AGENT_LLM_FALLBACK_MODEL")),
        )

    @property
    def project_prompt_dir(self) -> Path:
        return self.repo_root / "project_prompt"

    def ensure_ready(self) -> None:
        if self.mode != "fpga":
            raise ValueError(f"Unsupported mode: {self.mode}. MVP currently supports fpga only.")
        if self.llm_timeout_seconds <= 0:
            raise ValueError("DIGITAL_IC_AGENT_LLM_TIMEOUT_SECONDS must be greater than 0.")
        if self.llm_max_attempts < 1:
            raise ValueError("DIGITAL_IC_AGENT_LLM_MAX_ATTEMPTS must be at least 1.")
        if self.llm_retry_backoff_seconds < 0:
            raise ValueError("DIGITAL_IC_AGENT_LLM_RETRY_BACKOFF_SECONDS must be non-negative.")
        if self.llm_transport not in {"auto", "chat", "responses_background"}:
            raise ValueError(
                "DIGITAL_IC_AGENT_LLM_TRANSPORT must be one of: auto, chat, responses_background."
            )
        if self.dry_run:
            return
        if not self.api_key:
            raise RuntimeError(
                "DIGITAL_IC_AGENT_API_KEY is not set. Provide a compatible external API key or use --dry-run."
            )


def _coalesce_optional_str(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None
