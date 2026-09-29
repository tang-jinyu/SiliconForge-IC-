from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import secrets
import threading
from typing import Any

from fastapi import HTTPException, Request


SESSION_COOKIE_NAME = "digital_ic_agent_session"
AUTH_SUBJECT_METADATA_KEY = "auth_subject_id"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


@dataclass(frozen=True)
class AuthSession:
    subject_id: str
    display_name: str
    issued_at: str


@dataclass(frozen=True)
class SessionLLMConfig:
    api_key: str
    base_url: str | None = None
    model: str | None = None
    llm_transport: str | None = None
    temperature: float | None = None

    @property
    def api_key_hint(self) -> str:
        suffix = self.api_key[-4:] if len(self.api_key) >= 4 else self.api_key
        return f"***{suffix}"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "llm_transport": self.llm_transport,
            "temperature": self.temperature,
            "api_key_hint": self.api_key_hint,
        }

    def to_runtime_overrides(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url is not None:
            payload["base_url"] = self.base_url
        if self.model is not None:
            payload["model"] = self.model
        if self.llm_transport is not None:
            payload["llm_transport"] = self.llm_transport
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        return payload


class AuthManager:
    def __init__(
        self,
        *,
        access_password: str | None = None,
        session_secret: str | None = None,
        allow_shared_llm: bool = False,
        cookie_name: str = SESSION_COOKIE_NAME,
    ) -> None:
        self.access_password = access_password or None
        self.cookie_name = cookie_name
        self.enabled = bool(self.access_password)
        self.allow_shared_llm = bool(allow_shared_llm)
        self._session_secret = (session_secret or secrets.token_urlsafe(32)).encode("utf-8")
        self._llm_configs: dict[str, SessionLLMConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "AuthManager":
        return cls(
            access_password=os.getenv("DIGITAL_IC_AGENT_ACCESS_PASSWORD") or None,
            session_secret=os.getenv("DIGITAL_IC_AGENT_SESSION_SECRET") or None,
            allow_shared_llm=_env_flag("DIGITAL_IC_AGENT_ALLOW_SHARED_LLM", default=False),
        )

    def login(self, *, display_name: str, password: str, existing_session: AuthSession | None = None) -> tuple[AuthSession, str]:
        if not self.enabled:
            raise HTTPException(status_code=400, detail="Authentication is not enabled.")
        normalized_name = display_name.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Display name is required.")
        if password != self.access_password:
            raise HTTPException(status_code=401, detail="Invalid access password.")

        subject_id = existing_session.subject_id if existing_session is not None else secrets.token_hex(12)
        session = AuthSession(subject_id=subject_id, display_name=normalized_name, issued_at=_utcnow_iso())
        return session, self._encode_session(session)

    def read_session(self, request: Request) -> AuthSession | None:
        if not self.enabled:
            return None
        token = request.cookies.get(self.cookie_name)
        if not token:
            return None
        try:
            return self._decode_session(token)
        except Exception:
            return None

    def require_session(self, request: Request) -> AuthSession:
        session = self.read_session(request)
        if session is None:
            raise HTTPException(status_code=401, detail="Login required.")
        return session

    def clear_session_state(self, session: AuthSession | None) -> None:
        if session is None:
            return
        with self._lock:
            self._llm_configs.pop(session.subject_id, None)

    def save_llm_config(
        self,
        session: AuthSession,
        *,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        llm_transport: str | None = None,
        temperature: float | None = None,
    ) -> SessionLLMConfig:
        normalized_api_key = api_key.strip()
        if not normalized_api_key:
            raise HTTPException(status_code=400, detail="API key is required.")
        if llm_transport and llm_transport not in {"auto", "chat", "responses_background"}:
            raise HTTPException(status_code=400, detail="Unsupported transport.")
        config = SessionLLMConfig(
            api_key=normalized_api_key,
            base_url=base_url.strip() or None if base_url is not None else None,
            model=model.strip() or None if model is not None else None,
            llm_transport=llm_transport or None,
            temperature=temperature,
        )
        with self._lock:
            self._llm_configs[session.subject_id] = config
        return config

    def get_llm_config(self, session: AuthSession | None) -> SessionLLMConfig | None:
        if session is None:
            return None
        with self._lock:
            return self._llm_configs.get(session.subject_id)

    def resolve_runtime_llm_config(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        subject_id = metadata.get(AUTH_SUBJECT_METADATA_KEY)
        if not subject_id:
            return None
        with self._lock:
            config = self._llm_configs.get(str(subject_id))
        return config.to_runtime_overrides() if config is not None else None

    def build_session_payload(self, session: AuthSession | None) -> dict[str, Any]:
        llm_config = self.get_llm_config(session)
        return {
            "enabled": self.enabled,
            "authenticated": session is not None,
            "display_name": session.display_name if session is not None else None,
            "llm_config_saved": llm_config is not None,
            "llm_config": llm_config.to_public_dict() if llm_config is not None else None,
        }

    def owns_subject(self, metadata: dict[str, Any], session: AuthSession | None) -> bool:
        if not self.enabled:
            return True
        if session is None:
            return False
        return metadata.get(AUTH_SUBJECT_METADATA_KEY) == session.subject_id

    def _encode_session(self, session: AuthSession) -> str:
        payload = {
            "subject_id": session.subject_id,
            "display_name": session.display_name,
            "issued_at": session.issued_at,
        }
        encoded = _b64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self._session_secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_session(self, token: str) -> AuthSession:
        encoded, _, provided_signature = token.partition(".")
        if not encoded or not provided_signature:
            raise ValueError("Invalid session token.")
        expected_signature = hmac.new(self._session_secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise ValueError("Invalid session signature.")
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
        return AuthSession(
            subject_id=str(payload["subject_id"]),
            display_name=str(payload["display_name"]),
            issued_at=str(payload["issued_at"]),
        )


def _env_flag(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
