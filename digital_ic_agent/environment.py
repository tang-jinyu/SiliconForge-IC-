from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv


def load_project_environment(*, override_provider: bool = False) -> None:
    """Load project settings without overriding host/container variables.

    ``.env.stepfun`` remains the zero-configuration Windows development
    profile.  A server can select another ``.env.<profile>`` file with
    ``DIGITAL_IC_AGENT_ENV_PROFILE`` or inject values through Docker/systemd;
    explicit process environment variables always win.
    """
    repo_root = Path(__file__).resolve().parents[1]
    host_settings = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("DIGITAL_IC_AGENT_")
    }
    load_dotenv(repo_root / ".env", override=False)

    profile = os.getenv("DIGITAL_IC_AGENT_ENV_PROFILE", "").strip()
    if not profile and (repo_root / ".env.stepfun").exists():
        profile = "stepfun"
    if profile:
        safe_profile = "".join(character for character in profile if character.isalnum() or character in "-_")
        if safe_profile != profile:
            raise ValueError("DIGITAL_IC_AGENT_ENV_PROFILE contains unsupported characters.")
        # A named local profile should override generic .env defaults, while
        # explicit host/container variables must remain authoritative.
        load_dotenv(repo_root / f".env.{safe_profile}", override=True)
    os.environ.update(host_settings)
