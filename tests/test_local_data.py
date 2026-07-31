import tempfile
import unittest
from pathlib import Path

from capcut_sdk.cache import JsonCache
from capcut_sdk.search import RecordIndex


class LocalDataTests(unittest.TestCase):
    def test_cache_round_trip_and_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = JsonCache(Path(directory))
            cache.put("effects", "blur", {"items": [{"title": "Blur"}]})
            self.assertEqual(cache.get("effects", "blur")["items"][0]["title"], "Blur")
            cache.clear()
            self.assertIsNone(cache.get("effects", "blur"))

    def test_record_index_searches_selected_fields(self):
        index = RecordIndex()
        index.add_many([{"id": "1", "title": "Soft Blur"}, {"id": "2", "title": "Glow"}])
        self.assertEqual(index.search("blur", fields=["title"]), [{"id": "1", "title": "Soft Blur"}])
