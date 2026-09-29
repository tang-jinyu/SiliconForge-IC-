from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from digital_ic_agent.config import AppConfig
from digital_ic_agent.llm import (
    ExternalAPILLM,
    LLMRequestTimeoutError,
    reset_llm_capability_probe_cache,
    warm_llm_capability_probe,
)


def _make_blocking_chat_model(started: threading.Event, aborted: threading.Event):
    class BlockingChatOpenAI:
        def __init__(self, *args, http_client=None, **kwargs) -> None:
            self.http_client = http_client

        def invoke(self, messages):
            started.set()
            while True:
                if getattr(self.http_client, "closed", False):
                    aborted.set()
                    raise RuntimeError("client closed")
                time.sleep(0.02)

        def with_structured_output(self, schema):
            parent = self

            class Runnable:
                def invoke(self, messages):
                    return parent.invoke(messages)

            return Runnable()

    return BlockingChatOpenAI


class _BlockingHttpClient:
    def __init__(self, *args, **kwargs) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeBackgroundResponse:
    def __init__(
        self,
        *,
        response_id: str,
        status: str,
        output_text: str = "",
        error: object | None = None,
        incomplete_details: object | None = None,
    ) -> None:
        self.id = response_id
        self.status = status
        self.output_text = output_text
        self.error = error
        self.incomplete_details = incomplete_details


class _FakeResponsesApi:
    def __init__(self, response_id: str, started: threading.Event) -> None:
        self._response_id = response_id
        self._started = started
        self.cancelled_ids: list[str] = []
        self.completed_text = "background result"
        self.create_calls = 0
        self.deleted_ids: list[str] = []

    def create(self, **kwargs):
        self.create_calls += 1
        self._started.set()
        return _FakeBackgroundResponse(response_id=self._response_id, status="queued")

    def parse(self, **kwargs):
        self._started.set()
        return _FakeBackgroundResponse(response_id=self._response_id, status="queued")

    def retrieve(self, response_id: str, **kwargs):
        if response_id in self.cancelled_ids:
            return _FakeBackgroundResponse(response_id=response_id, status="cancelled")
        return _FakeBackgroundResponse(response_id=response_id, status="in_progress", output_text=self.completed_text)

    def cancel(self, response_id: str, **kwargs):
        self.cancelled_ids.append(response_id)
        return _FakeBackgroundResponse(response_id=response_id, status="cancelled")

    def delete(self, response_id: str, **kwargs):
        self.deleted_ids.append(response_id)


class _UnsupportedResponsesApi(_FakeResponsesApi):
    def create(self, **kwargs):
        self.create_calls += 1
        raise RuntimeError("responses background unsupported")


class _FakeCompletedResponsesApi(_FakeResponsesApi):
    def __init__(self, response_id: str, started: threading.Event, output_text: str) -> None:
        super().__init__(response_id, started)
        self.completed_text = output_text

    def retrieve(self, response_id: str, **kwargs):
        return _FakeBackgroundResponse(response_id=response_id, status="completed", output_text=self.completed_text)


class _FakeOpenAIClient:
    def __init__(self, responses_api) -> None:
        self.responses = responses_api
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _CancellationSignal(RuntimeError):
    pass


class _StructuredPayload(BaseModel):
    summary: str


class LlmAbortTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_llm_capability_probe_cache()

    def test_invoke_text_times_out_and_closes_inflight_request(self) -> None:
        started = threading.Event()
        aborted = threading.Event()
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url="https://example.invalid",
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=0.1,
            llm_transport="chat",
        )
        llm = ExternalAPILLM(config)

        with patch("digital_ic_agent.llm.ChatOpenAI", _make_blocking_chat_model(started, aborted)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                with self.assertRaises(LLMRequestTimeoutError) as context:
                    llm.invoke_text("system", "user", operation_label="generate_spec:llm")

        self.assertTrue(started.is_set())
        self.assertTrue(aborted.wait(timeout=1))
        self.assertIn("generate_spec:llm", str(context.exception))

    def test_invoke_structured_cancels_and_closes_inflight_request(self) -> None:
        started = threading.Event()
        aborted = threading.Event()
        cancel_requested = threading.Event()
        failure_holder: dict[str, BaseException] = {}
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url="https://example.invalid",
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=5.0,
            llm_transport="chat",
        )

        def cancellation_check(stage: str) -> None:
            if cancel_requested.is_set():
                raise _CancellationSignal(stage)

        llm = ExternalAPILLM(config, cancellation_check=cancellation_check)

        def worker() -> None:
            try:
                llm.invoke_structured(
                    "system",
                    "user",
                    _StructuredPayload,
                    operation_label="analyze_requirement:llm",
                )
            except BaseException as exc:
                failure_holder["error"] = exc

        with patch("digital_ic_agent.llm.ChatOpenAI", _make_blocking_chat_model(started, aborted)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                self.assertTrue(started.wait(timeout=5))
                cancel_requested.set()
                thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertTrue(aborted.wait(timeout=1))
        self.assertIsInstance(failure_holder.get("error"), _CancellationSignal)
        self.assertEqual(str(failure_holder["error"]), "analyze_requirement:llm")

    def test_invoke_text_timeout_cancels_provider_response(self) -> None:
        started = threading.Event()
        responses_api = _FakeResponsesApi("resp-timeout", started)
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url=None,
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=0.1,
            llm_transport="responses_background",
        )
        llm = ExternalAPILLM(config)

        with patch("digital_ic_agent.llm.OpenAI", lambda **kwargs: _FakeOpenAIClient(responses_api)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                with self.assertRaises(LLMRequestTimeoutError):
                    llm.invoke_text("system", "user", operation_label="generate_spec:llm")

        self.assertTrue(started.is_set())
        self.assertEqual(responses_api.cancelled_ids, ["resp-timeout"])

    def test_invoke_structured_cancel_calls_provider_cancel(self) -> None:
        started = threading.Event()
        responses_api = _FakeResponsesApi("resp-cancel", started)
        cancel_requested = threading.Event()
        failure_holder: dict[str, BaseException] = {}
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url=None,
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=5.0,
            llm_transport="responses_background",
        )

        def cancellation_check(stage: str) -> None:
            if cancel_requested.is_set():
                raise _CancellationSignal(stage)

        llm = ExternalAPILLM(config, cancellation_check=cancellation_check)

        def worker() -> None:
            try:
                llm.invoke_structured(
                    "system",
                    "user",
                    _StructuredPayload,
                    operation_label="analyze_requirement:llm",
                )
            except BaseException as exc:
                failure_holder["error"] = exc

        with patch("digital_ic_agent.llm.OpenAI", lambda **kwargs: _FakeOpenAIClient(responses_api)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                self.assertTrue(started.wait(timeout=5))
                cancel_requested.set()
                thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(responses_api.cancelled_ids, ["resp-cancel"])
        self.assertIsInstance(failure_holder.get("error"), _CancellationSignal)

    def test_auto_transport_uses_background_responses_for_native_openai(self) -> None:
        started = threading.Event()
        responses_api = _FakeCompletedResponsesApi("resp-ok", started, '{"summary":"ok"}')
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url=None,
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=5.0,
            llm_transport="auto",
        )
        llm = ExternalAPILLM(config)

        with patch("digital_ic_agent.llm.OpenAI", lambda **kwargs: _FakeOpenAIClient(responses_api)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                result = llm.invoke_structured(
                    "system",
                    "user",
                    _StructuredPayload,
                    operation_label="analyze_requirement:llm",
                )

        self.assertEqual(llm.transport, "responses_background")
        self.assertTrue(started.is_set())
        self.assertEqual(result.summary, "ok")

    def test_startup_probe_enables_background_transport_for_supported_custom_base_url(self) -> None:
        started = threading.Event()
        responses_api = _FakeResponsesApi("resp-probe", started)
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url="https://custom.provider.invalid/v1",
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=5.0,
            llm_transport="auto",
        )

        with patch("digital_ic_agent.llm.OpenAI", lambda **kwargs: _FakeOpenAIClient(responses_api)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                first = warm_llm_capability_probe(config)
                second = warm_llm_capability_probe(config)
                llm = ExternalAPILLM(config)

        self.assertEqual(first["source"], "startup_probe")
        self.assertTrue(first["supports_responses_background"])
        self.assertEqual(second["source"], "startup_probe")
        self.assertEqual(responses_api.create_calls, 1)
        self.assertEqual(llm.transport, "responses_background")
        self.assertEqual(responses_api.cancelled_ids, ["resp-probe"])
        self.assertEqual(responses_api.deleted_ids, ["resp-probe"])

    def test_startup_probe_falls_back_to_chat_for_unsupported_custom_base_url(self) -> None:
        started = threading.Event()
        responses_api = _UnsupportedResponsesApi("resp-probe-fail", started)
        config = AppConfig(
            model="fake-model",
            api_key="test-key",
            base_url="https://custom.provider.invalid/v1",
            temperature=0.0,
            mode="fpga",
            dry_run=False,
            repo_root=Path("."),
            llm_timeout_seconds=5.0,
            llm_transport="auto",
        )

        with patch("digital_ic_agent.llm.OpenAI", lambda **kwargs: _FakeOpenAIClient(responses_api)):
            with patch("digital_ic_agent.llm.httpx.Client", _BlockingHttpClient):
                result = warm_llm_capability_probe(config)
                llm = ExternalAPILLM(config)

        self.assertEqual(result["source"], "startup_probe_failed")
        self.assertFalse(result["supports_responses_background"])
        self.assertEqual(responses_api.create_calls, 1)
        self.assertEqual(llm.transport, "chat")


if __name__ == "__main__":
    unittest.main()