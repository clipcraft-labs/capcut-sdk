"""Report non-secret structural properties of captured signature headers."""

from __future__ import annotations

import base64
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from mitmproxy import http


SIGNATURES = {
    "x-argus",
    "x-gorgon",
    "x-khronos",
    "x-ladon",
    "x-ss-req-ticket",
    "x-ss-stub",
}
ROOT = Path(__file__).resolve().parents[2]


def openapi_paths() -> set[str]:
    return {
        line.strip()[:-1]
        for line in (ROOT / "openapi.yaml").read_text().splitlines()
        if line.startswith("  /") and line.endswith(":")
    }


def shape(name: str, value: str) -> str:
    if name in {"x-argus", "x-ladon"}:
        try:
            decoded = base64.b64decode(value, validate=True)
        except ValueError:
            return f"chars={len(value)} encoding=invalid-base64"
        return f"chars={len(value)} bytes={len(decoded)} encoding=base64"
    if name == "x-gorgon":
        return f"chars={len(value)} version={value[:4]}"
    return f"chars={len(value)}"


class Inventory:
    def __init__(self):
        self.rows = defaultdict(set)
        self.paths = openapi_paths()

    def request(self, flow: http.HTTPFlow):
        path = urlsplit(flow.request.pretty_url).path
        if path not in self.paths:
            return
        for name in SIGNATURES:
            value = flow.request.headers.get(name)
            if value:
                self.rows[(path, name)].add(shape(name, value))

    def done(self):
        for (path, name), shapes in sorted(self.rows.items()):
            print(f"path={path} header={name} shapes={';'.join(sorted(shapes))}")


addons = [Inventory()]
