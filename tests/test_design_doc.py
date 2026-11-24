"""Checks that docs/design.md covers ticket #5's "Done when" items and leaks no IP addresses."""
import re
import unittest
from pathlib import Path

DESIGN = Path(__file__).parent.parent / "docs" / "design.md"


class DesignDocTest(unittest.TestCase):
    def setUp(self):
        self.text = DESIGN.read_text(encoding="utf-8")

    def test_export_folder(self):
        self.assertIn("/srv/mc-export", self.text)

    def test_interval(self):
        self.assertTrue("60" in self.text or "every minute" in self.text.lower())

    def test_web_container(self):
        self.assertIn("CT 101", self.text)

    def test_port(self):
        self.assertIn("8080", self.text)

    def test_tailscale(self):
        self.assertIn("Tailscale", self.text)

    def test_no_port_forwarding_statement(self):
        self.assertRegex(self.text.lower(), r"no (router )?port forward")

    def test_no_ipv4_addresses(self):
        self.assertIsNone(re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", self.text))


if __name__ == "__main__":
    unittest.main()
