"""Cursor-paginated template clients."""

from dataclasses import dataclass
from typing import Any

from .models import CursorPage
from .transport import HttpTransport


@dataclass(frozen=True, slots=True)
class TemplateCollection:
    id: str
    display_name: str
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TemplateCollection":
        return cls(str(value.get("id") or ""), str(value.get("display_name") or ""), value)


@dataclass(frozen=True, slots=True)
class Template:
    id: str
    title: str
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Template":
        return cls(str(value.get("id") or ""), str(value.get("title") or ""), value)


class TemplatesClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def collections(self, *, collection_type: int = 0, sdk_version: str = "9.1.0") -> list[TemplateCollection]:
        body = {"collection_type": collection_type, "sdk_version": sdk_version}
        data = self._transport.post("/lv/v1/pc/replicate/get_collections", params=_params(self._transport.config), json_body=body, base_url=self._transport.config.base_url).get("data") or {}
        return [TemplateCollection.from_dict(value) for value in data.get("collections") or []]

    def list(self, collection_id: str | int, *, cursor: str | int = 0, count: int = 32, scene: str = "edit_page-Template", sdk_version: str = "9.1.0") -> CursorPage[Template]:
        body = {"id": collection_id, "cursor": cursor, "count": count, "scene": scene, "sdk_version": sdk_version}
        data = self._transport.post("/lv/v1/pc/replicate/get_collection_templates", params=_params(self._transport.config), json_body=body, base_url=self._transport.config.base_url).get("data") or {}
        return CursorPage([Template.from_dict(value) for value in data.get("item_list") or []], str(data.get("new_cursor")) if data.get("new_cursor") is not None else None, bool(data.get("has_more")), data)

    def iter(self, collection_id: str | int, *, cursor: str | int = 0, count: int = 32, scene: str = "edit_page-Template", sdk_version: str = "9.1.0"):
        """Yield every cursor page while the API reports more results."""
        while True:
            page = self.list(collection_id, cursor=cursor, count=count, scene=scene, sdk_version=sdk_version)
            yield page
            if not page.has_more or page.next_cursor is None or page.next_cursor == str(cursor):
                return
            cursor = page.next_cursor


def _params(config) -> list[tuple[str, str]]:
    return [("aid", str(config.app_id)), ("app_name", config.app_name), ("device_id", config.device.device_id), ("device_platform", config.device.device_platform), ("version_code", config.version_code)]
