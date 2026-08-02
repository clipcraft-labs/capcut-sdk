"""Stable catalogue records for draft compilers, CLIs, and MCP servers."""

from dataclasses import asdict, dataclass
import json
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

# Values observed in Desktop's mget_artist_item response.  Prefer the typed
# response branch below because it is self-describing; effect_type remains a
# useful fallback for transition records, which currently have no dedicated
# top-level payload branch.
EFFECT_TYPE_KINDS = {
    1: "text-effect",
    2: "sticker",
    5: "stock-video",
    7: "effect",
    8: "body-effect",
    9: "image",
    10: "font",
    12: "filter",
    13: "animation",
    18: "text-animation",
    19: "transition",
    26: "audio-effect",
    35: "animation",
    48: "caption-template",
    97: "mask",
}


def infer_effect_kind(effect: Effect, *, panel: str | None = None) -> str:
    """Infer render semantics from a Desktop catalogue/mget record."""
    raw = effect.raw or {}
    if isinstance(raw.get("filter"), dict):
        return "filter"
    if isinstance(raw.get("subtitle_template"), dict):
        return "caption-template"
    if isinstance(raw.get("sticker"), dict):
        return "sticker"
    if isinstance(raw.get("font"), dict):
        return "font"
    if isinstance(raw.get("text_animation"), dict):
        return "text-animation"
    if isinstance(raw.get("animation"), dict):
        animation_type = str(raw["animation"].get("animation_type") or "")
        return "text-animation" if animation_type.startswith("text_") else "animation"
    if isinstance(raw.get("word_art"), dict):
        return "text-effect"
    if isinstance(raw.get("audio_effect"), dict):
        return "audio-effect"
    attr = raw.get("common_attr") if isinstance(raw.get("common_attr"), dict) else raw
    try:
        effect_type = int(attr.get("effect_type"))
    except (TypeError, ValueError):
        effect_type = None
    if effect_type in EFFECT_TYPE_KINDS:
        return EFFECT_TYPE_KINDS[effect_type]
    panel_kind = PANEL_KINDS.get(panel or "")
    return panel_kind or "material"


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_http_url(value: Any) -> str | None:
    """Return the first provider URL from a scalar or nested URL collection."""
    if isinstance(value, str):
        return value if value.startswith(("https://", "http://")) else None
    if isinstance(value, dict):
        for child in value.values():
            found = _first_http_url(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_http_url(child)
            if found:
                return found
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
    download_url: str | None = None
    file_md5: str | None = None
    metadata: dict[str, Any] | None = None

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
        download_url = _recursive_first(raw, "download_url", "file_url", "resource_url", "zip_url")
        download_info = attr.get("download_info") if isinstance(attr.get("download_info"), dict) else {}
        if not download_url and download_info.get("url"):
            download_url = download_info["url"]
        if not download_url:
            # Desktop catalogue responses commonly expose the signed resource
            # archive as common_attr.item_urls[0], while download_info.url is
            # present but empty.  Preserve that URL in the lock record so an
            # ID selected by the CLI is sufficient for the packaging step.
            download_url = _first_http_url(_recursive_first(raw, "item_urls"))
        file_md5 = _recursive_first(raw, "file_md5", "md5", "resource_md5")
        metadata: dict[str, Any] = {}
        try:
            extra = json.loads(str(attr.get("extra") or "{}"))
        except (TypeError, ValueError):
            extra = {}
        try:
            sdk_extra = json.loads(str(attr.get("sdk_extra") or "{}"))
        except (TypeError, ValueError):
            sdk_extra = {}
        animation = raw.get("text_animation") or raw.get("animation")
        if isinstance(animation, dict) and animation.get("animation_type"):
            provider_type = str(animation["animation_type"])
            metadata["animation_type"] = {
                "video_group": "group", "text_xunhuan": "loop"
            }.get(provider_type, provider_type)
        if extra.get("complex_video_mask"):
            metadata["resource_type"] = str(extra["complex_video_mask"])
        if extra.get("effect_duration") is not None:
            metadata["default_duration_ms"] = extra["effect_duration"]
        if isinstance(sdk_extra, dict) and sdk_extra:
            metadata["sdk_extra"] = sdk_extra
        if attr.get("effect_type") is not None:
            metadata["effect_type"] = attr["effect_type"]
        media_duration = None
        if isinstance(raw.get("video"), dict):
            media_duration = _first(raw["video"], "duration", "duration_ms")
        return cls(
            provider="capcut",
            kind=kind or infer_effect_kind(effect, panel=panel),
            id=identifier,
            name=effect.title,
            effect_id=str(effect_id) if effect_id is not None else identifier,
            resource_id=str(resource_id),
            category=category,
            vip=effect.is_vip,
            commercial=bool(commercial) if commercial is not None else None,
            download_url=str(download_url) if download_url else None,
            duration=media_duration,
            file_md5=str(file_md5) if file_md5 else None,
            metadata=metadata or None,
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


def _recursive_first(value: Any, *keys: str) -> Any:
    """Find provider fields despite panel-specific response nesting."""
    if isinstance(value, dict):
        direct = _first(value, *keys)
        if direct is not None:
            return direct
        for child in value.values():
            found = _recursive_first(child, *keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _recursive_first(child, *keys)
            if found is not None:
                return found
    return None
