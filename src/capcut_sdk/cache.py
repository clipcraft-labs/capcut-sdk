"""Small JSON cache for sanitized, user-owned API results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonCache:
    """Persist JSON payloads outside the repository with deterministic keys."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        directory = self.root / namespace
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return directory / f"{digest}.json"

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, namespace: str, key: str, payload: dict[str, Any]) -> Path:
        path = self._path(namespace, key)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)
        return path

    def clear(self) -> None:
        for path in self.root.rglob("*.json"):
            path.unlink()
