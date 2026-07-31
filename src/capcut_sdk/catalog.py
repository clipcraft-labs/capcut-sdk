"""Stable catalogue records for draft compilers, CLIs, and MCP servers."""

from dataclasses import asdict, dataclass
from typing import Any

from .models import Effect, PanelCategory
from .music import MusicCollection, Song

PANEL_KINDS = {
    "effects2": "effect",
    "transitions": "transition",
    "filter": "filter",
    "face-prop": "body-effect",
    "subtitle-templates": "caption-template",
    "default": "material",
}


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


@dataclass(frozen=True, slots=True)
class CatalogCategory:
    panel: str
    id: str
    key: str
    name: str = ""


@dataclass(frozen=True, slots=True)
class CatalogResource:
    provider: str
    kind: str
    id: str
    name: str
    effect_id: str | None = None
    resource_id: str | None = None
    category: CatalogCategory | None = None
    vip: bool | None = None
    commercial: bool | None = None
    preview_url: str | None = None
    duration: int | float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_effect(
        cls,
        effect: Effect,
        *,
        kind: str | None = None,
        panel: str | None = None,
        category_id: str | int | None = None,
        category_key: str | None = None,
        category_name: str = "",
    ) -> "CatalogResource":
        raw = effect.raw or {}
        attr = raw.get("common_attr") or raw
        resource = raw.get("resource") if isinstance(raw.get("resource"), dict) else {}
        identifier = str(_first(attr, "id", "resource_id", "effect_id") or effect.id)
        effect_id = _first(raw, "effect_id") or _first(attr, "effect_id") or _first(resource, "effect_id")
        resource_id = _first(raw, "resource_id") or _first(attr, "resource_id") or _first(resource, "resource_id") or identifier
        category = None
        if panel is not None:
            category = CatalogCategory(panel, str(category_id or ""), category_key or "", category_name)
        commercial = _first(raw, "is_commerce", "is_commercial")
        return cls(
            provider="capcut",
            kind=kind or PANEL_KINDS.get(panel or "", "effect"),
            id=identifier,
            name=effect.title,
            effect_id=str(effect_id) if effect_id is not None else identifier,
            resource_id=str(resource_id),
            category=category,
            vip=effect.is_vip,
            commercial=bool(commercial) if commercial is not None else None,
        )

    @classmethod
    def from_song(cls, song: Song) -> "CatalogResource":
        raw = song.raw or {}
        commercial = _first(raw, "is_commerce", "is_commercial")
        return cls(
            provider="capcut",
            kind="music",
            id=song.id,
            name=song.title,
            commercial=bool(commercial) if commercial is not None else None,
            preview_url=str(raw.get("preview_url")) if raw.get("preview_url") else None,
            duration=song.duration,
        )

    @classmethod
    def from_collection(cls, collection: MusicCollection, *, effects: bool = False) -> "CatalogResource":
        return cls(
            provider="capcut",
            kind="sound-effect-collection" if effects else "music-collection",
            id=collection.id,
            name=collection.name,
        )


def category_record(category: PanelCategory, *, panel: str) -> dict[str, Any]:
    return asdict(CatalogCategory(panel, category.category_id, category.category_key, category.category_name))
