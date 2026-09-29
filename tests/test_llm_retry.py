import unittest
from unittest.mock import patch

from digital_ic_agent.config import AppConfig
from digital_ic_agent.llm import ExternalAPILLM, LLMRequestTimeoutError


class LlmRetryTest(unittest.TestCase):
    def test_timeout_retries_and_uses_fallback_model_on_last_attempt(self):
        config = AppConfig(
            model="step-primary",
            api_key=None,
            base_url="https://api.stepfun.com/v1",
            temperature=0,
            mode="fpga",
            dry_run=True,
            repo_root=None,
            llm_timeout_seconds=1,
            llm_transport="chat",
            llm_max_attempts=2,
            llm_retry_backoff_seconds=0,
            llm_fallback_model="step-fallback",
        )
        llm = ExternalAPILLM(config)
        seen_models = []

        def fake_once(_invoke, *, operation_label, model_name):
            seen_models.append(model_name)
            if len(seen_models) == 1:
                raise LLMRequestTimeoutError(operation_label, 1)
            return "ok"

        with patch.object(llm, "_invoke_with_chat_monitor_once", side_effect=fake_once):
            result = llm._invoke_with_chat_monitor(lambda _model: "unused", operation_label="retry-test")

        self.assertEqual(result, "ok")
        self.assertEqual(seen_models, ["step-primary", "step-fallback"])
        self.assertEqual(llm._trace_state["retry_count"], 1)
        self.assertTrue(llm._trace_state["fallback_used"])


if __name__ == "__main__":
    unittest.main()
