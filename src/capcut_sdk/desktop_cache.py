"""Read CapCut Desktop's Resource SDK HTTP cache without launching Desktop."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator

from .models import Effect


def default_ressdk_roots() -> tuple[Path, ...]:
    """Return known macOS and Windows Resource SDK database roots."""
    home = Path.home()
    candidates = (
        home / "Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Cache/ressdk_db",
        home / "Movies/CapCut/User Data/Cache/ressdk_db",
        home / "AppData/Local/CapCut/User Data/Cache/ressdk_db",
        home / "AppData/Roaming/CapCut/User Data/Cache/ressdk_db",
    )
    override = os.environ.get("CAPCUT_RESSDK_DB_ROOT")
    return ((Path(override).expanduser(),) if override else ()) + candidates


def _resource_records(value: Any) -> Iterator[dict[str, Any]]:
    """Yield typed artist records embedded anywhere in a cached response."""
    if isinstance(value, dict):
        attr = value.get("common_attr")
        if isinstance(attr, dict) and (attr.get("id") or attr.get("resource_id")):
            yield value
            return
        for child in value.values():
            yield from _resource_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _resource_records(child)


class DesktopCacheCatalog:
    """Exact/search access to cached Resource SDK responses.

    Databases are opened using SQLite's read-only URI mode. This class never
    starts CapCut and never modifies Desktop state.
    """

    def __init__(self, roots: Iterable[str | Path] = ()):
        self.roots = tuple(Path(root).expanduser() for root in roots) or default_ressdk_roots()

    def databases(self) -> tuple[Path, ...]:
        found: set[Path] = set()
        for root in self.roots:
            if root.is_file() and root.name == "rp.db":
                found.add(root.resolve())
            elif root.is_dir():
                found.update(path.resolve() for path in root.glob("*/rp.db") if path.is_file())
                if (root / "rp.db").is_file():
                    found.add((root / "rp.db").resolve())
        return tuple(sorted(found))

    def _records(self) -> Iterator[tuple[str, dict[str, Any]]]:
        for database in self.databases():
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            try:
                try:
                    rows = connection.execute(
                        "SELECT COALESCE(timestamp, ''), response_body FROM http_cache "
                        "WHERE response_body IS NOT NULL ORDER BY timestamp"
                    )
                except sqlite3.DatabaseError:
                    continue
                for timestamp, body in rows:
                    try:
                        payload = json.loads(body)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    for record in _resource_records(payload):
                        yield str(timestamp or ""), record
            finally:
                connection.close()

    def get_by_ids(self, resource_ids: Iterable[str]) -> list[Effect]:
        wanted = {str(resource_id) for resource_id in resource_ids}
        selected: dict[str, tuple[str, dict[str, Any]]] = {}
        if not wanted:
            return []
        for timestamp, record in self._records():
            attr = record.get("common_attr") or record
            identifier = str(attr.get("id") or attr.get("resource_id") or attr.get("effect_id") or "")
            if identifier in wanted and (identifier not in selected or timestamp >= selected[identifier][0]):
                selected[identifier] = (timestamp, record)
        return [Effect.from_dict(selected[item][1]) for item in resource_ids if str(item) in selected]

    def search(self, query: str, *, limit: int = 20) -> list[Effect]:
        needle = query.casefold()
        selected: dict[str, tuple[str, dict[str, Any]]] = {}
        for timestamp, record in self._records():
            effect = Effect.from_dict(record)
            if effect.id and needle in effect.title.casefold() and (
                effect.id not in selected or timestamp >= selected[effect.id][0]
            ):
                selected[effect.id] = (timestamp, record)
        return [Effect.from_dict(value[1]) for value in selected.values()][:limit]
