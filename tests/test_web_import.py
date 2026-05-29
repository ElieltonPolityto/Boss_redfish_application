import unittest
from pathlib import Path

from boss_redfish.web_import import manual_import_steps


class WebImportTests(unittest.TestCase):
    def test_manual_import_steps_point_to_redfish_server_and_template(self):
        steps = manual_import_steps(Path("dist/example.zip"))

        self.assertIn("Data Transfer > Redfish Server", steps)
        self.assertIn("dist/example.zip", steps)
        self.assertIn("Start", steps)


if __name__ == "__main__":
    unittest.main()
