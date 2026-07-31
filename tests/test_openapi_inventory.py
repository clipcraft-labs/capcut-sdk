import unittest
from pathlib import Path

from tools.openapi_inventory import inventory


class OpenAPIInventoryTests(unittest.TestCase):
    def test_inventory_matches_declared_operation_count(self):
        operations = inventory(Path("openapi.yaml"))
        self.assertEqual(len(operations), 23)
        self.assertEqual(sum(item["status"] == "stable" for item in operations), 10)
        self.assertTrue(all(item["path"].startswith("/") for item in operations))
