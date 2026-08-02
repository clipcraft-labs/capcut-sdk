import unittest

from tools.sanitize_fixture import sanitize


class SanitizeFixtureTests(unittest.TestCase):
    def test_removes_sensitive_fields_and_url_query_secrets(self):
        signed_url = "https://cdn.example/x.webp?" + "x-signature=secret&size=small"
        result = sanitize({"device_id": "secret", "title": "Blur", "cover_url": signed_url, "nested": [{"uid": "secret"}]})
        self.assertEqual(result["device_id"], "<redacted>")
        self.assertEqual(result["nested"][0]["uid"], "<redacted>")
        self.assertIn("x-signature=%3Credacted%3E", result["cover_url"])
        self.assertIn("size=small", result["cover_url"])
