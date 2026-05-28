import unittest
from pathlib import Path

from boss_redfish.discovery import normalize_boss_urls
from boss_redfish.web_import import ImportResult, assisted_import_template, manual_import_steps


class WebImportTests(unittest.TestCase):
    def test_manual_import_steps_point_to_redfish_server_and_template(self):
        steps = manual_import_steps(Path("dist/example.zip"))

        self.assertIn("Data Transfer > Redfish Server", steps)
        self.assertIn("dist/example.zip", steps)
        self.assertIn("Start", steps)

    def test_assisted_import_falls_back_when_no_browser_runner_is_available(self):
        urls = normalize_boss_urls("http://192.0.2.10/boss/")

        result = assisted_import_template(
            urls=urls,
            web_user="operator",
            web_password="dummy-password",
            template_zip=Path("dist/example.zip"),
            browser_runner=None,
        )

        self.assertIsInstance(result, ImportResult)
        self.assertFalse(result.ok)
        self.assertFalse(result.automated)
        self.assertIn("Importacao manual", result.message)


if __name__ == "__main__":
    unittest.main()
