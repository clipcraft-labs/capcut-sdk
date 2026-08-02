import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.public_audit import PUBLIC_MEDIA_SHA256, audit


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

    def test_allows_only_the_pinned_public_example_video(self):
        relative, expected = next(iter(PUBLIC_MEDIA_SHA256.items()))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / relative
            video.parent.mkdir(parents=True)
            # Use a tiny fixture and temporarily pin its digest so the test
            # covers both the path and content requirements.
            video.write_bytes(b"redistributable-example")
            PUBLIC_MEDIA_SHA256[relative] = hashlib.sha256(video.read_bytes()).hexdigest()
            try:
                self.assertEqual(audit(root), [])
                video.write_bytes(b"changed")
                self.assertEqual(audit(root), [str(video)])
            finally:
                PUBLIC_MEDIA_SHA256[relative] = expected
