"""AIGC helper clients."""

from typing import Any

from .errors import ApiError
from .transport import HttpTransport


class AIGCClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def random_prompts(self, model_list: list[str], *, scene: str) -> dict[str, list[str]]:
        body = {"model_list": model_list, "scene": scene}
        data = self._transport.post("/artist/v1/aigc_effect/random_prompt", params=_params(self._transport.config), json_body=body, base_url=self._transport.config.editor_base_url).get("data") or {}
        return {str(key): list(value or []) for key, value in (data.get("model2prompt_list") or {}).items()}

    def user_list(self, *, effect_type: int = 0, count: int = 20, offset: int = 0) -> dict[str, Any]:
        body = {"effect_type": effect_type, "count": count, "offset": offset}
        return self._transport.post("/artist/v1/aigc_effect/user_aigc_list", params=_params(self._transport.config), json_body=body)


def _params(config) -> list[tuple[str, str]]:
    return [("aid", str(config.app_id)), ("device_id", config.device.device_id), ("language", config.language), ("region", config.region)]
