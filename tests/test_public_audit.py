import tempfile
import unittest
from pathlib import Path

from tools.public_audit import audit


class PublicAuditTests(unittest.TestCase):
    def test_detects_secret_like_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("Cookie" + ": secret\n", encoding="utf-8")
            self.assertEqual(len(audit(root)), 1)

    def test_ignores_private_capture_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "captures"
            private.mkdir()
            (private / "raw.json").write_text("Cookie" + ": secret\n", encoding="utf-8")
            self.assertEqual(audit(root), [])
