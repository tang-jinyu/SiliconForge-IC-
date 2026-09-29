from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
import time
from typing import Any, Callable, Literal, Type, TypeVar
from urllib.parse import urlparse

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from .config import AppConfig


_CALL_POLL_INTERVAL_SECONDS = 0.2
_ABORT_JOIN_TIMEOUT_SECONDS = 5.0
_CAPABILITY_PROBE_TIMEOUT_SECONDS = 5.0
_T = TypeVar("_T")
LLMTransport = Literal["chat", "responses_background"]
_CAPABILITY_PROBE_CACHE: dict[str, dict[str, Any]] = {}
_CAPABILITY_PROBE_LOCK = threading.Lock()


class LLMRequestTimeoutError(TimeoutError):
    def __init__(self, operation_label: str, timeout_seconds: float) -> None:
        super().__init__(f"LLM request timed out after {timeout_seconds:.1f}s during {operation_label}.")
        self.operation_label = operation_label
        self.timeout_seconds = timeout_seconds


class ExternalAPILLM:
    def __init__(
        self,
        config: AppConfig,
        *,
        cancellation_check: Callable[[str], None] | None = None,
        trace_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        config.ensure_ready()
        self._config = config
        self._cancellation_check = cancellation_check
        self._trace_update = trace_update
        self._capability_probe = warm_llm_capability_probe(config)
        self._transport = _resolve_transport(config, self._capability_probe)
        self._trace_state: dict[str, Any] = {}
        self._record_trace(
            {
                "transport": self._transport,
                "transport_requested": self._config.llm_transport,
                "response_id": None,
                "response_status": "idle",
                "capability_probe": self._capability_probe,
            }
        )

    def invoke_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        *,
        operation_label: str = "llm:structured",
    ) -> BaseModel:
        try:
            if self._transport == "responses_background":
                return self._invoke_structured_with_responses_background(
                    system_prompt,
                    user_prompt,
                    schema,
                    operation_label=operation_label,
                )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            return self._invoke_with_chat_monitor(
                lambda model: model.with_structured_output(schema).invoke(messages),
                operation_label=operation_label,
            )
        except BadRequestError as exc:
            if not _supports_prompted_json_fallback(exc):
                raise
            fallback_prompt = _build_prompted_json_request(user_prompt, schema)
            response_text = self.invoke_text(
                system_prompt,
                fallback_prompt,
                operation_label=f"{operation_label}:json_fallback",
            )
            payload = _extract_json_payload(response_text)
            return schema.model_validate(payload)

    def invoke_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        operation_label: str = "llm:text",
    ) -> str:
        if self._transport == "responses_background":
            return self._invoke_text_with_responses_background(
                system_prompt,
                user_prompt,
                operation_label=operation_label,
            )
        response = self._invoke_with_chat_monitor(
            lambda model: model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            ),
            operation_label=operation_label,
        )
        return _extract_text(response.content)

    def _build_model(self, http_client: httpx.Client, model_name: str | None = None) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_name or self._config.model,
            api_key=self._config.api_key,
            base_url=self._config.base_url,
            temperature=self._config.temperature,
            timeout=self._config.llm_timeout_seconds,
            http_client=http_client,
        )

    def _build_openai_client(self, http_client: httpx.Client) -> OpenAI:
        return OpenAI(
            api_key=self._config.api_key,
            base_url=self._config.base_url,
            timeout=self._config.llm_timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )

    def _invoke_with_chat_monitor(
        self,
        invoke: Callable[[ChatOpenAI], _T],
        *,
        operation_label: str,
    ) -> _T:
        retry_history: list[dict[str, Any]] = []
        max_attempts = self._config.llm_max_attempts
        for attempt in range(1, max_attempts + 1):
            use_fallback = bool(
                attempt == max_attempts
                and self._config.llm_fallback_model
                and self._config.llm_fallback_model != self._config.model
            )
            model_name = self._config.llm_fallback_model if use_fallback else self._config.model
            self._record_trace({
                "attempt": attempt,
                "max_attempts": max_attempts,
                "active_model": model_name,
                "fallback_used": use_fallback,
                "retry_history": list(retry_history),
            })
            try:
                return self._invoke_with_chat_monitor_once(
                    invoke,
                    operation_label=operation_label,
                    model_name=str(model_name),
                )
            except BaseException as exc:
                if attempt >= max_attempts or not _is_retryable_llm_error(exc):
                    raise
                retry_history.append({
                    "attempt": attempt,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                })
                self._record_trace({
                    "response_status": "retry_wait",
                    "retry_count": len(retry_history),
                    "retry_history": list(retry_history),
                })
                self._wait_for_retry(operation_label, attempt)
        raise RuntimeError("unreachable")

    def _invoke_with_chat_monitor_once(
        self,
        invoke: Callable[[ChatOpenAI], _T],
        *,
        operation_label: str,
        model_name: str,
    ) -> _T:
        self._check_cancellation(operation_label)
        self._record_trace(
            {
                "last_operation_label": operation_label,
                "response_id": None,
                "response_status": "in_progress",
                "provider_cancel_requested": False,
                "provider_cancel_completed": False,
            }
        )
        http_client = httpx.Client(timeout=self._config.llm_timeout_seconds)
        model = self._build_model(http_client, model_name)
        completed = threading.Event()
        outcome: dict[str, Any] = {}

        def worker() -> None:
            try:
                outcome["result"] = invoke(model)
            except BaseException as exc:
                outcome["error"] = exc
            finally:
                completed.set()

        thread = threading.Thread(target=worker, name=f"llm-{operation_label}", daemon=True)
        thread.start()
        deadline = time.monotonic() + self._config.llm_timeout_seconds

        try:
            while not completed.wait(_CALL_POLL_INTERVAL_SECONDS):
                self._check_cancellation(operation_label)
                if time.monotonic() >= deadline:
                    self._record_trace({"response_status": "timed_out"})
                    _close_resource(http_client)
                    thread.join(timeout=_ABORT_JOIN_TIMEOUT_SECONDS)
                    raise LLMRequestTimeoutError(operation_label, self._config.llm_timeout_seconds)
        except BaseException:
            self._record_trace({"response_status": "aborted"})
            _close_resource(http_client)
            thread.join(timeout=_ABORT_JOIN_TIMEOUT_SECONDS)
            raise
        finally:
            if completed.is_set():
                _close_resource(http_client)

        if "error" in outcome:
            self._record_trace({"response_status": "failed", "last_error": str(outcome["error"])})
            raise outcome["error"]
        self._record_trace({"response_status": "completed", "last_error": None})
        return outcome["result"]

    def _wait_for_retry(self, operation_label: str, attempt: int) -> None:
        delay = self._config.llm_retry_backoff_seconds * (2 ** (attempt - 1))
        deadline = time.monotonic() + delay
        while True:
            self._check_cancellation(f"{operation_label}:retry_wait")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(_CALL_POLL_INTERVAL_SECONDS, remaining))

    def _invoke_text_with_responses_background(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        operation_label: str,
    ) -> str:
        response = self._run_responses_background_request(
            lambda client: client.responses.create(
                model=self._config.model,
                instructions=system_prompt,
                input=user_prompt,
                temperature=self._config.temperature,
                background=True,
            ),
            operation_label=operation_label,
        )
        return response.output_text

    def _invoke_structured_with_responses_background(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        *,
        operation_label: str,
    ) -> BaseModel:
        response = self._run_responses_background_request(
            lambda client: client.responses.parse(
                model=self._config.model,
                instructions=system_prompt,
                input=user_prompt,
                temperature=self._config.temperature,
                text_format=schema,
                background=True,
            ),
            operation_label=operation_label,
        )
        return schema.model_validate_json(response.output_text)

    def _run_responses_background_request(
        self,
        start_request: Callable[[OpenAI], Any],
        *,
        operation_label: str,
    ) -> Any:
        self._check_cancellation(operation_label)
        self._record_trace(
            {
                "last_operation_label": operation_label,
                "response_id": None,
                "response_status": "submitting",
                "provider_cancel_requested": False,
                "provider_cancel_completed": False,
            }
        )
        http_client = httpx.Client(timeout=self._config.llm_timeout_seconds)
        client = self._build_openai_client(http_client)

        try:
            initial_response = start_request(client)
            response_id = str(initial_response.id)
            self._record_trace(
                {
                    "response_id": response_id,
                    "response_status": str(getattr(initial_response, "status", "queued")).lower(),
                }
            )
            return self._poll_background_response(
                client,
                response_id,
                operation_label=operation_label,
            )
        except BaseException as exc:
            if not isinstance(exc, LLMRequestTimeoutError):
                self._record_trace({"response_status": "failed", "last_error": str(exc)})
            raise
        finally:
            _close_resource(client)
            _close_resource(http_client)

    def _poll_background_response(
        self,
        client: OpenAI,
        response_id: str,
        *,
        operation_label: str,
    ) -> Any:
        deadline = time.monotonic() + self._config.llm_timeout_seconds

        while True:
            try:
                self._check_cancellation(operation_label)
            except BaseException:
                self._cancel_provider_response(client, response_id)
                raise

            response = client.responses.retrieve(
                response_id,
                timeout=self._config.llm_timeout_seconds,
            )
            status = str(getattr(response, "status", "")).lower()
            self._record_trace({"response_id": response_id, "response_status": status})
            if status == "completed":
                self._record_trace({"last_error": None})
                return response
            if status in {"failed", "incomplete", "cancelled"}:
                raise RuntimeError(_describe_response_failure(response, operation_label))

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._cancel_provider_response(client, response_id)
                self._record_trace({"response_status": "timed_out"})
                raise LLMRequestTimeoutError(operation_label, self._config.llm_timeout_seconds)
            time.sleep(min(_CALL_POLL_INTERVAL_SECONDS, remaining))

    def _check_cancellation(self, operation_label: str) -> None:
        if self._cancellation_check is not None:
            self._cancellation_check(operation_label)

    @property
    def transport(self) -> LLMTransport:
        return self._transport

    def _cancel_provider_response(self, client: OpenAI, response_id: str) -> None:
        self._record_trace(
            {
                "response_id": response_id,
                "provider_cancel_requested": True,
                "provider_cancel_completed": False,
            }
        )
        try:
            client.responses.cancel(
                response_id,
                timeout=self._config.llm_timeout_seconds,
            )
            self._record_trace(
                {
                    "response_id": response_id,
                    "response_status": "cancelled",
                    "provider_cancel_completed": True,
                }
            )
        except Exception:
            return

    def _record_trace(self, updates: dict[str, Any]) -> None:
        payload = dict(self._trace_state)
        payload.update(updates)
        payload["updated_at"] = _utcnow_iso()
        self._trace_state = payload
        if self._trace_update is not None:
            self._trace_update(dict(payload))


def _close_resource(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            return


def _is_retryable_llm_error(exc: BaseException) -> bool:
    if isinstance(exc, (LLMRequestTimeoutError, httpx.TimeoutException, httpx.TransportError)):
        return True
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return status_code == 429 or (isinstance(status_code, int) and status_code >= 500)


def warm_llm_capability_probe_from_env() -> dict[str, Any] | None:
    config = AppConfig.from_env(mode="fpga", dry_run=False)
    return warm_llm_capability_probe(config)


def warm_llm_capability_probe(config: AppConfig) -> dict[str, Any] | None:
    if config.dry_run or not config.api_key:
        return None
    if config.llm_transport == "chat":
        return {
            "base_url": config.base_url,
            "checked_at": _utcnow_iso(),
            "supports_responses_background": False,
            "source": "explicit_chat",
            "detail": "Transport is pinned to chat; startup probe skipped.",
        }
    if config.llm_transport == "responses_background":
        return {
            "base_url": config.base_url,
            "checked_at": _utcnow_iso(),
            "supports_responses_background": True,
            "source": "explicit_responses_background",
            "detail": "Transport is pinned to responses_background; startup probe skipped.",
        }
    if _uses_native_openai_endpoint(config.base_url):
        return {
            "base_url": config.base_url,
            "checked_at": _utcnow_iso(),
            "supports_responses_background": True,
            "source": "native_openai_default",
            "detail": "Native OpenAI endpoint detected; Responses background transport is enabled by default.",
        }

    cache_key = _capability_probe_cache_key(config)
    with _CAPABILITY_PROBE_LOCK:
        cached = _CAPABILITY_PROBE_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    result = _run_capability_probe(config)
    with _CAPABILITY_PROBE_LOCK:
        _CAPABILITY_PROBE_CACHE[cache_key] = dict(result)
    return result


def reset_llm_capability_probe_cache() -> None:
    with _CAPABILITY_PROBE_LOCK:
        _CAPABILITY_PROBE_CACHE.clear()


def _resolve_transport(config: AppConfig, capability_probe: dict[str, Any] | None) -> LLMTransport:
    if config.llm_transport == "chat":
        return "chat"
    if config.llm_transport == "responses_background":
        return "responses_background"
    if capability_probe and capability_probe.get("supports_responses_background"):
        return "responses_background"
    return "chat"


def _capability_probe_cache_key(config: AppConfig) -> str:
    return f"{config.base_url or 'native'}|{config.model}"


def _run_capability_probe(config: AppConfig) -> dict[str, Any]:
    timeout_seconds = min(config.llm_timeout_seconds, _CAPABILITY_PROBE_TIMEOUT_SECONDS)
    http_client = httpx.Client(timeout=timeout_seconds)
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=timeout_seconds,
        max_retries=0,
        http_client=http_client,
    )
    response_id: str | None = None

    try:
        response = client.responses.create(
            model=config.model,
            input="capability probe",
            instructions="Return OK.",
            background=True,
            max_output_tokens=1,
            store=False,
        )
        response_id = str(response.id)
        return {
            "base_url": config.base_url,
            "checked_at": _utcnow_iso(),
            "supports_responses_background": True,
            "source": "startup_probe",
            "detail": (
                "Startup capability probe accepted Responses background requests"
                f" with status '{str(getattr(response, 'status', 'queued')).lower()}'."
            ),
        }
    except Exception as exc:
        return {
            "base_url": config.base_url,
            "checked_at": _utcnow_iso(),
            "supports_responses_background": False,
            "source": "startup_probe_failed",
            "detail": f"{exc.__class__.__name__}: {exc}",
        }
    finally:
        if response_id is not None:
            try:
                client.responses.cancel(response_id, timeout=timeout_seconds)
            except Exception:
                pass
            delete = getattr(client.responses, "delete", None)
            if callable(delete):
                try:
                    delete(response_id, timeout=timeout_seconds)
                except Exception:
                    pass
        _close_resource(client)
        _close_resource(http_client)


def _uses_native_openai_endpoint(base_url: str | None) -> bool:
    if not base_url:
        return True
    parsed = urlparse(base_url)
    host = (parsed.netloc or parsed.path).lower()
    return host.endswith("api.openai.com") or "api.openai.com" in host


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _describe_response_failure(response: Any, operation_label: str) -> str:
    status = str(getattr(response, "status", "unknown"))
    error = getattr(response, "error", None)
    incomplete_details = getattr(response, "incomplete_details", None)
    if error is not None:
        message = getattr(error, "message", None) or str(error)
        return f"LLM background response failed during {operation_label}: {message}"
    if incomplete_details is not None:
        reason = getattr(incomplete_details, "reason", None) or str(incomplete_details)
        return f"LLM background response incomplete during {operation_label}: {reason}"
    return f"LLM background response ended with status '{status}' during {operation_label}."


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


def _supports_prompted_json_fallback(exc: BadRequestError) -> bool:
    message = str(exc).lower()
    return "response_format" in message and "unavailable" in message


def _build_prompted_json_request(user_prompt: str, schema: Type[BaseModel]) -> str:
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=True, indent=2)
    return (
        f"{user_prompt}\n\n"
        "Return exactly one JSON object that matches the JSON Schema below. "
        "Do not include markdown, code fences, or any explanatory text.\n\n"
        f"JSON Schema:\n{schema_text}"
    )


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    candidates = [stripped]
    if stripped.startswith("```"):
        fence_lines = stripped.splitlines()
        if len(fence_lines) >= 3:
            candidates.append("\n".join(fence_lines[1:-1]).strip())

    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        candidates.append(stripped[first_brace : last_brace + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    raise ValueError(f"Model did not return a valid JSON object: {stripped[:400]}")
