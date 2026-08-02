import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

from capcut_sdk import CatalogResource, DesktopCacheCatalog


class DesktopCacheCatalogTests(unittest.TestCase):
    def test_exact_lookup_reads_http_cache_without_writing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile"
            profile.mkdir()
            database = profile / "rp.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE http_cache (timestamp TEXT, response_body TEXT)")
            connection.execute("INSERT INTO http_cache VALUES (?, ?)", ("2026-01-01", json.dumps({
                "data": {"effects": [{
                    "common_attr": {
                        "id": "7653734580033178887", "title": "Blind wipe",
                        "effect_type": 13,
                        "item_urls": ["https://example.test/animation.zip"],
                        "file_md5": "abc123",
                    },
                    "animation": {"animation_type": "video_group"},
                }]}
            })))
            connection.commit()
            connection.close()
            before = database.stat().st_mtime_ns

            items = DesktopCacheCatalog([root]).get_by_ids(["7653734580033178887"])

            self.assertEqual(len(items), 1)
            resource = CatalogResource.from_effect(items[0])
            self.assertEqual(resource.kind, "animation")
            self.assertEqual(resource.download_url, "https://example.test/animation.zip")
            self.assertEqual(resource.file_md5, "abc123")
            self.assertEqual(database.stat().st_mtime_ns, before)

    def test_type_inference_for_desktop_resource_branches(self):
        fixtures = (
            ({"font": {}, "common_attr": {"id": "1", "effect_type": 10}}, "font"),
            ({"text_animation": {}, "common_attr": {"id": "2", "effect_type": 18}}, "text-animation"),
            ({"word_art": {}, "common_attr": {"id": "3", "effect_type": 1}}, "text-effect"),
            ({"common_attr": {"id": "4", "effect_type": 26}}, "audio-effect"),
            ({"common_attr": {"id": "5", "effect_type": 97}}, "mask"),
        )
        from capcut_sdk.models import Effect
        for raw, expected in fixtures:
            with self.subTest(expected=expected):
                self.assertEqual(CatalogResource.from_effect(Effect.from_dict(raw)).kind, expected)
