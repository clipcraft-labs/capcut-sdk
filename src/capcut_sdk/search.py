"""Dependency-free local search over normalized SDK records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class RecordIndex:
    """Index JSON-like records for case-insensitive substring search."""

    def __init__(self):
        self._records: list[dict[str, Any]] = []

    def add(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def add_many(self, records: Iterable[dict[str, Any]]) -> None:
        self._records.extend(records)

    def search(self, query: str, *, fields: Iterable[str] | None = None) -> list[dict[str, Any]]:
        needle = query.casefold()
        names = tuple(fields) if fields is not None else ()
        result = []
        for record in self._records:
            values = (record.get(name) for name in names) if names else record.values()
            if any(needle in str(value).casefold() for value in values):
                result.append(record)
        return result

    def __len__(self) -> int:
        return len(self._records)
