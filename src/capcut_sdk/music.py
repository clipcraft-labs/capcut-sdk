"""Music collection and song clients."""

from dataclasses import dataclass
from typing import Any

from .models import Page
from .transport import HttpTransport


@dataclass(frozen=True, slots=True)
class MusicCollection:
    id: str
    name: str
    collection_type: int | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MusicCollection":
        return cls(str(value.get("id") or ""), str(value.get("name") or ""), value.get("collection_type"), value)


@dataclass(frozen=True, slots=True)
class Song:
    id: str
    title: str
    author: str = ""
    duration: int | float | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Song":
        return cls(str(value.get("id") or ""), str(value.get("title") or ""), str(value.get("author") or ""), value.get("duration"), value)


class MusicClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def collections(self, *, collection_type: int = 0, effects: bool = False, only_commercial: bool = False) -> list[MusicCollection]:
        path = "/lv/v1/get_music_effect_collections" if effects else "/lv/v1/get_collections"
        body = {"only_commercial": only_commercial} if effects else {"collection_type": collection_type}
        data = self._transport.post(path, params=_params(self._transport.config), json_body=body, base_url=self._transport.config.editor_base_url).get("data") or {}
        return [MusicCollection.from_dict(value) for value in data.get("collections") or []]

    def songs(self, collection_id: str | int, *, collection_type: int = 0, count: int = 20, offset: int = 0) -> Page[Song]:
        body = {"collection_type": collection_type, "count": count, "id": collection_id, "offset": offset, "filter_commercial": False, "only_enterprise_commercial": False}
        data = self._transport.post("/lv/v1/get_collection_songs", params=_params(self._transport.config), json_body=body, base_url=self._transport.config.editor_base_url).get("data") or {}
        return Page([Song.from_dict(value) for value in data.get("songs") or []], data.get("next_offset"), bool(data.get("has_more")), data)

    def iter_songs(self, collection_id: str | int, *, collection_type: int = 0, count: int = 20, offset: int = 0):
        """Yield every song page while the API reports more results."""
        while True:
            page = self.songs(collection_id, collection_type=collection_type, count=count, offset=offset)
            yield page
            if not page.has_more or page.next_offset is None or page.next_offset == offset:
                return
            offset = page.next_offset

    def find_song_by_id(self, song_id: str | int, *, count: int = 50) -> tuple[Song, MusicCollection] | None:
        """Find an exact song ID through Desktop's current music catalogue.

        Desktop 9.1.0 contains a ``multi_get_songs`` request type, but its
        wire format has not been verified.  Scanning the advertised
        collections is slower, but it gives an exact, evidence-backed fallback
        without guessing a private request schema.
        """
        target = str(song_id)
        seen: set[str] = set()
        for collection in self.collections():
            if not collection.id or collection.id in seen:
                continue
            seen.add(collection.id)
            collection_type = collection.collection_type or 0
            for page in self.iter_songs(collection.id, collection_type=collection_type, count=count):
                for song in page.items:
                    if song.id == target:
                        return song, collection
        return None


def _params(config) -> list[tuple[str, str]]:
    return [("aid", str(config.app_id)), ("device_id", config.device.device_id), ("language", config.language), ("region", config.region)]
