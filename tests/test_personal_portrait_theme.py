from __future__ import annotations

import unittest
from pathlib import Path


class PersonalPortraitThemeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.html = (cls.repo_root / "digital_ic_agent" / "web" / "index.html").read_text(encoding="utf-8")
        cls.css = (cls.repo_root / "digital_ic_agent" / "web" / "styles.css").read_text(encoding="utf-8")
        cls.js = (cls.repo_root / "digital_ic_agent" / "web" / "app.js").read_text(encoding="utf-8")

    def test_home_contains_portrait_upload_controls_and_three_ribbons(self) -> None:
        self.assertIn('id="profile-photo"', self.html)
        self.assertIn('id="portrait-upload"', self.html)
        self.assertIn('id="portrait-reset"', self.html)
        self.assertEqual(self.html.count("photo-ribbon__track"), 3)

    def test_custom_portrait_updates_main_photo_and_ribbon_theme(self) -> None:
        self.assertIn("siliconforge.customPortrait.v1", self.js)
        self.assertIn("createPortraitDataUrl", self.js)
        self.assertIn("--custom-portrait", self.js)
        self.assertIn("body.has-custom-portrait .photo-ribbon__frame", self.css)

    def test_default_portrait_assets_are_present(self) -> None:
        for filename in ("1.jpg", "2.jpg", "3.jpg", "4.jpg", "5jpg.jpg", "6.jpg", "7.jpg"):
            self.assertTrue((self.repo_root / "picture" / filename).is_file(), filename)


if __name__ == "__main__":
    unittest.main()
