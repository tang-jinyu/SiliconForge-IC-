from __future__ import annotations

import sys
import unittest
from pathlib import Path

from digital_ic_agent.eda import _run_subprocess, _simulation_log_has_self_check_failures


class EdaSubprocessTest(unittest.TestCase):
    def test_run_subprocess_handles_large_output_without_deadlock(self) -> None:
        command = [
            sys.executable,
            "-c",
            (
                "import os\n"
                "payload = (b'x' * 4096) + b'\\n'\n"
                "for _ in range(128):\n"
                "    os.write(1, payload)\n"
                "    os.write(2, payload)\n"
            ),
        ]

        completed = _run_subprocess(command, cwd=Path.cwd(), timeout_seconds=2)

        self.assertEqual(completed.returncode, 0, completed.stderr[-1000:])
        self.assertNotIn("Process timed out", completed.stderr)
        self.assertGreater(len(completed.stdout), 100000)
        self.assertGreater(len(completed.stderr), 100000)

    def test_self_check_treats_error_lines_as_failure(self) -> None:
        log = "[vvp] returncode=0\n\n[stdout]\nERROR: Test did not complete\n"

        self.assertTrue(_simulation_log_has_self_check_failures(log))


if __name__ == "__main__":
    unittest.main()