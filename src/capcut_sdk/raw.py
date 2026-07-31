"""Escape hatch for OpenAPI operations without a typed domain adapter yet."""

from typing import Any

from .transport import HttpTransport


class RawAPIClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def post(self, path: str, body: dict[str, Any], *, params: list[tuple[str, str]] | None = None, service: str | None = None) -> dict[str, Any]:
        base_url = f"https://{service}.capcutapi.com" if service else None
        return self._transport.post(path, params=params or [], json_body=body, base_url=base_url)

    def get(self, path: str, *, params: list[tuple[str, str]] | None = None, service: str | None = None) -> dict[str, Any]:
        base_url = f"https://{service}.capcutapi.com" if service else None
        return self._transport.get(path, params=params or [], base_url=base_url)
