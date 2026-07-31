"""Inventory non-user-specific MSSDK context from OpenAPI captures.

Device/install IDs, tokens, cookies, signatures, and request bodies are never
printed. Only application and SDK build metadata is reported.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from mitmproxy import http


ROOT = Path(__file__).resolve().parents[2]
SAFE_FIELDS = {
    "aid",
    "app_id",
    "app_name",
    "version_code",
    "version_name",
    "sdk_version",
    "sdk_version_code",
    "channel",
    "device_platform",
    "device_type",
    "os_version",
}


def openapi_paths() -> set[str]:
    return {
        line.strip()[:-1]
        for line in (ROOT / "openapi.yaml").read_text().splitlines()
        if line.startswith("  /") and line.endswith(":")
    }


class Inventory:
    def __init__(self):
        self.paths = openapi_paths()
        self.values = defaultdict(set)

    def request(self, flow: http.HTTPFlow):
        split = urlsplit(flow.request.pretty_url)
        if split.path not in self.paths:
            return
        for name, value in parse_qsl(split.query, keep_blank_values=True):
            if name in SAFE_FIELDS and value:
                self.values[name].add(value)

    def done(self):
        for name in sorted(self.values):
            print(f"{name}={','.join(sorted(self.values[name]))}")


addons = [Inventory()]
