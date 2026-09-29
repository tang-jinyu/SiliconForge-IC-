from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "competition"
BASE_URL = "http://127.0.0.1:8000"


def shot(page, name: str) -> None:
    page.screenshot(path=str(OUT / name), full_page=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_function("document.body.dataset.appReady === 'true'", timeout=20_000)
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "gui_01_home.png")

        page.locator('.view-tab[data-flow-key="digital_ic_workflow"]').click()
        page.locator("#requirement-text").fill(
            "设计一个 66×66 位无符号乘法器。输入为 a[65:0] 与 b[65:0]，输出 product[131:0]；"
            "组合逻辑实现，要求生成可综合 RTL、自检查测试平台、规格说明、仿真和综合报告。"
        )
        page.locator("#title").fill("66×66 位乘法器完整闭环演示")
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "gui_02_workflow_input.png")

        page.locator('.view-tab[data-screen="library"]').click()
        page.locator("#screen-library").wait_for(state="visible")
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "gui_03_template_library.png")

        page.locator('.view-tab[data-screen="workspace"]').click()
        page.locator("#screen-workspace").wait_for(state="visible")
        first_detail = page.locator('.task-card [data-task-action="detail"]').first
        if first_detail.count():
            first_detail.click()
            page.locator("#task-detail .detail-head").wait_for(state="visible", timeout=15_000)
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "gui_04_workspace.png")

        quality = page.locator("#detail-section-quality")
        if quality.count():
            quality.scroll_into_view_if_needed()
            shot(page, "gui_05_quality.png")

        editor = page.locator("#detail-section-editor")
        if editor.count():
            editor.scroll_into_view_if_needed()
            shot(page, "gui_06_editor.png")
        browser.close()


if __name__ == "__main__":
    main()
