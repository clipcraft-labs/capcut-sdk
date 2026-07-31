"""Small response models shared by generated and hand-written resources."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: list[T]
    next_offset: int | None = None
    has_more: bool = False
    raw: dict[str, Any] | None = None

    def __iter__(self):
        return iter(self.items)


@dataclass(frozen=True, slots=True)
class CursorPage(Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Effect:
    id: str
    title: str
    is_vip: bool | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Effect":
        attr = value.get("common_attr") or value
        is_vip = None
        try:
            import json
            is_vip = json.loads(attr.get("extra") or "{}").get("is_vip")
        except (TypeError, ValueError):
            pass
        return cls(str(attr.get("id") or attr.get("effect_id") or ""), str(attr.get("title") or ""), is_vip, value)


@dataclass(frozen=True, slots=True)
class PanelCategory:
    category_id: str
    category_key: str
    category_name: str
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PanelCategory":
        return cls(str(value.get("category_id") or ""), str(value.get("category_key") or ""), str(value.get("category_name") or ""), value)


@dataclass(frozen=True, slots=True)
class PanelInfo:
    categories: list[PanelCategory]
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SearchWords:
    default_word: str
    recommend_words: list[str]
    hot_words: list[dict[str, Any]]
    raw: dict[str, Any] | None = None
