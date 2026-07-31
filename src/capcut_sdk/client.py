"""Top-level SDK client and first capture-backed resource."""

from typing import Any

from .config import SDKConfig
from .models import Effect, Page, PanelCategory, PanelInfo, SearchWords
from .music import MusicClient
from .templates import TemplatesClient
from .aigc import AIGCClient
from .raw import RawAPIClient
from .configuration import ConfigurationClient
from .transport import HttpTransport, Signer


class EffectsClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def list(self, *, category_id: int = 18885, category: str = "hot", panel: str = "effects2", count: int = 50, offset: int = 0) -> Page[Effect]:
        body = {
            "app_id": self._transport.config.app_id,
            "category_id": category_id,
            "category_key": category,
            "count": count,
            "offset": offset,
            "panel": panel,
            "panel_source": "heycan",
            "full_count": False,
            "filter_optional": {"filter_uncommercial": False, "no_copyrighted": False, "no_tuchong_order": False, "only_enterprise_commercial": False},
            "statistics_optional": {"need_add_count": False, "need_favorite_count": False, "need_usage_count": False},
        }
        data = self._transport.post("/artist/v1/effect/get_resources_by_category_id", params=_common_params(self._transport.config), json_body=body).get("data") or {}
        items = [Effect.from_dict(item) for item in data.get("effect_item_list") or []]
        return Page(items, data.get("next_offset"), bool(data.get("has_more")), data)

    def iter_pages(self, *, category_id: int = 18885, category: str = "hot", panel: str = "effects2", count: int = 50, offset: int = 0):
        while True:
            page = self.list(category_id=category_id, category=category, panel=panel, count=count, offset=offset)
            yield page
            if not page.has_more or page.next_offset is None or page.next_offset == offset:
                return
            offset = page.next_offset

    def search(self, query: str, *, effect_type: int = 7, count: int = 50, offset: int = 0) -> Page[Effect]:
        body = {"app_id": self._transport.config.app_id, "query": query, "effect_type": effect_type, "count": count, "offset": offset, "need_recommend": True}
        data = self._transport.post("/artist/v1/effect/search", params=_common_params(self._transport.config), json_body=body).get("data") or {}
        items = [Effect.from_dict(item) for item in data.get("effect_item_list") or []]
        return Page(items, data.get("next_offset"), bool(data.get("has_more")), data)

    def search_words(self, *, effect_type: int = 7) -> SearchWords:
        body = {"app_id": self._transport.config.app_id, "effect_type": effect_type}
        data = self._transport.post("/artist/v1/effect/get_search_words", params=_common_params(self._transport.config), json_body=body).get("data") or {}
        return SearchWords(str(data.get("default_word") or ""), list(data.get("recommend_words") or []), list(data.get("hot_words") or []), data)


class PanelsClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def info(self, *, panel: str = "effects2", full_count: bool = False, get_resource: bool = False) -> PanelInfo:
        body = {"panel": panel, "full_count": full_count, "get_resource": get_resource}
        data = self._transport.post("/artist/v1/panel/get_panel_info", params=_common_params(self._transport.config), json_body=body).get("data") or {}
        categories = [PanelCategory.from_dict(value) for value in data.get("categories") or []]
        return PanelInfo(categories, data)


def _common_params(config: SDKConfig) -> list[tuple[str, str]]:
    return [("aid", str(config.app_id)), ("app_name", config.app_name), ("device_id", config.device.device_id), ("device_platform", config.device.device_platform), ("language", config.language), ("region", config.region), ("version_code", config.version_code), ("version_name", config.version_name), ("iid", config.device.iid)]


class CapCutClient:
    def __init__(self, config: SDKConfig, *, signer: Signer | None = None, transport: HttpTransport | None = None):
        self.config = config
        self.transport = transport or HttpTransport(config, signer=signer)
        self.effects = EffectsClient(self.transport)
        self.panels = PanelsClient(self.transport)
        self.music = MusicClient(self.transport)
        self.templates = TemplatesClient(self.transport)
        self.aigc = AIGCClient(self.transport)
        self.raw = RawAPIClient(self.transport)
        self.configuration = ConfigurationClient(self.transport)
