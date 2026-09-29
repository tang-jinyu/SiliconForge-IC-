from __future__ import annotations

import unittest

from pydantic import ValidationError

from digital_ic_agent.api import TaskSubmissionPayload


class TaskSubmissionPayloadTest(unittest.TestCase):
    def test_workflow_accepts_title_as_short_problem_statement(self) -> None:
        payload = TaskSubmissionPayload(
            title="设计一个 FIFO",
            task_kind="digital_ic_workflow",
            requirement_text="",
        )

        self.assertEqual(payload.requirement_text, "设计一个 FIFO")

    def test_workflow_still_rejects_completely_empty_input(self) -> None:
        with self.assertRaises(ValidationError):
            TaskSubmissionPayload(task_kind="digital_ic_workflow")


if __name__ == "__main__":
    unittest.main()
