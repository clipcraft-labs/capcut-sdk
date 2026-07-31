"""Configuration endpoints with intentionally flexible response models."""

from typing import Any

from .transport import HttpTransport


class ConfigurationClient:
    def __init__(self, transport: HttpTransport):
        self._transport = transport

    def effect_general_config(self, *, scene: str) -> dict[str, Any]:
        return self._transport.post("/artist/v1/effect/general_config", params=[("language", self._transport.config.language)], json_body={"scene": scene}).get("data") or {}

    def remote_settings(self) -> dict[str, Any]:
        return self._transport.get("/service/settings/v3/", params=[("aid", str(self._transport.config.app_id)), ("device_id", self._transport.config.device.device_id), ("version_code", self._transport.config.version_code)], base_url=self._transport.config.editor_base_url)

    def model_arithmetics(self, required_model_list: str) -> dict[str, Any]:
        params = [("required_model_list", required_model_list), ("aid", str(self._transport.config.app_id)), ("device_id", self._transport.config.device.device_id), ("region", self._transport.config.region), ("version_code", self._transport.config.version_code)]
        return self._transport.get("/model/api/arithmetics", params=params, base_url=self._transport.config.editor_base_url)
