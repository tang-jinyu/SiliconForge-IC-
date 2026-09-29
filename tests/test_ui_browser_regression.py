from __future__ import annotations

import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

import uvicorn

from digital_ic_agent.api import build_app
from digital_ic_agent.task_queue import FileTaskQueue
from digital_ic_agent.task_service import AgentTaskService

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - handled by skip
    PlaywrightError = Exception
    PlaywrightTimeoutError = Exception
    sync_playwright = None


def _svg_payload(fill: str, label: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
        f'<rect width="640" height="360" rx="28" fill="{fill}"/>'
        f'<path d="M40 220 L120 180 L180 205 L250 120 L320 140 L390 90 L470 170 L560 110 L600 140" '
        f'stroke="#ffffff" stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<text x="44" y="66" font-size="34" font-family="Segoe UI, Arial" fill="#ffffff">{label}</text>'
        "</svg>"
    ).encode("utf-8")


class UiBrowserRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.service = AgentTaskService(
            repo_root=self.repo_root,
            queue=FileTaskQueue(self.repo_root / ".agent_queue"),
        )
        self.port = self._find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                build_app(service=self.service),
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
            )
        )
        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()
        self._wait_for_server()

    def tearDown(self) -> None:
        self.server.should_exit = True
        self.server_thread.join(timeout=10)
        self.temp_dir.cleanup()

    def test_submit_cancel_retry_detail_and_cover_switch(self) -> None:
        if sync_playwright is None:
            self.skipTest("playwright is not installed")

        title = f"ui-regression-{int(time.time() * 1000)}"

        with sync_playwright() as playwright:
            browser = self._launch_browser(playwright)
            page = browser.new_page()
            try:
                page.goto(self.base_url, wait_until="domcontentloaded")
                self._wait_for_app_ready(page)
                page.locator('.view-tab[data-flow-key="rtl_module_generation"]').click()
                page.locator("#screen-studio").wait_for(state="visible", timeout=10000)
                page.locator("#title").wait_for(state="visible", timeout=10000)
                page.locator("#title").fill(title)
                page.locator("#requirement-text").fill(
                    "Generate a simple GPIO debounce module with a deterministic self-checking testbench."
                )
                page.locator('#task-form button[type="submit"]').click()

                card = page.locator(".task-card").filter(has_text=title).first
                card.wait_for(state="visible", timeout=10000)
                card.locator('[data-task-action="detail"]').click()

                page.locator("#task-detail .detail-head h3").wait_for(state="visible", timeout=10000)
                self.assertEqual(page.locator("#task-detail .detail-head h3").first.text_content(), title)

                self._upload_asset(
                    card=card,
                    page=page,
                    asset_type="board_photo",
                    caption="board hero",
                    file_name="board.svg",
                    file_bytes=_svg_payload("#ff9966", "Board Hero"),
                    is_cover=True,
                )
                card = page.locator(".task-card").filter(has_text=title).first
                self._upload_asset(
                    card=card,
                    page=page,
                    asset_type="waveform_capture",
                    caption="wave timing",
                    file_name="wave.svg",
                    file_bytes=_svg_payload("#66ccff", "Wave Timing"),
                    is_cover=False,
                )

                page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('#task-detail .detail-asset-card--coverable')).some((node) => node.textContent?.includes('wave timing'))",
                    timeout=15000,
                )
                waveform_asset = page.locator("#task-detail .detail-asset-card--coverable").filter(has_text="wave timing").first
                waveform_asset.locator('[data-asset-action="cover"]').click()
                page.wait_for_function(
                    "(taskTitle) => { const card = Array.from(document.querySelectorAll('.task-card')).find((node) => node.textContent.includes(taskTitle)); return Boolean(card && card.textContent.includes('waveform_capture · cover')); }",
                    arg=title,
                    timeout=10000,
                )
                page.wait_for_function(
                    "() => document.querySelector('#task-detail')?.textContent.includes('波形缩略卡')",
                    timeout=10000,
                )

                card.locator('[data-task-action="cancel"]').click()
                page.wait_for_function(
                    "(taskTitle) => { const card = Array.from(document.querySelectorAll('.task-card')).find((node) => node.textContent.includes(taskTitle)); const badge = card?.querySelector('.status-badge'); return Boolean(badge && badge.textContent.includes('已取消')); }",
                    arg=title,
                    timeout=10000,
                )

                card.locator('[data-task-action="retry"]').click()
                page.wait_for_function(
                    "(taskTitle) => Array.from(document.querySelectorAll('.task-card')).filter((node) => node.textContent.includes(taskTitle)).length >= 2",
                    arg=title,
                    timeout=10000,
                )
                page.wait_for_function(
                    "() => document.querySelector('#task-detail')?.textContent.includes('_retry1')",
                    timeout=10000,
                )
            finally:
                browser.close()

    def _upload_asset(
        self,
        *,
        card,
        page,
        asset_type: str,
        caption: str,
        file_name: str,
        file_bytes: bytes,
        is_cover: bool,
    ) -> None:
        task_id = card.get_attribute("data-task-id")
        self.assertIsNotNone(task_id)

        for attempt in range(2):
            live_card = page.locator(f'.task-card[data-task-id="{task_id}"]').first
            live_card.locator(".asset-type-select").select_option(asset_type)
            live_card.locator(".asset-caption-input").fill(caption)
            checkbox = live_card.locator(".asset-cover-checkbox")
            if is_cover:
                checkbox.check()
            else:
                checkbox.uncheck()
            live_card.locator(".asset-file-input").set_input_files(
                [{"name": file_name, "mimeType": "image/svg+xml", "buffer": file_bytes}]
            )

            try:
                with page.expect_response(
                    lambda response: response.request.method == "GET"
                    and f"/api/tasks/{task_id}/detail" in response.url
                    and response.ok,
                    timeout=15000,
                ):
                    with page.expect_response(
                        lambda response: response.request.method == "POST"
                        and f"/api/tasks/{task_id}/assets" in response.url
                        and response.ok,
                        timeout=15000,
                    ):
                        live_card.locator(".asset-upload-button").click()
                return
            except PlaywrightTimeoutError:
                if attempt == 1:
                    raise

    def _launch_browser(self, playwright):
        last_error: Exception | None = None
        for launch_kwargs in (
            {"headless": True, "channel": "msedge"},
            {"headless": True, "channel": "chrome"},
            {"headless": True},
        ):
            try:
                return playwright.chromium.launch(**launch_kwargs)
            except PlaywrightError as exc:
                last_error = exc
        self.skipTest(f"no Playwright browser is available: {last_error}")

    def _wait_for_server(self) -> None:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        self.fail("local UI test server did not start in time")

    @staticmethod
    def _wait_for_app_ready(page) -> None:
        page.wait_for_function(
            "() => document.body.dataset.appReady === 'true'",
            timeout=15000,
        )

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])


if __name__ == "__main__":
    unittest.main()