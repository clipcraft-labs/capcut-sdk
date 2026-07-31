"""HTTP transport boundary. Signing is injected, never hard-coded into resources."""

from typing import Any, Protocol

import httpx

from .config import SDKConfig
from .errors import ApiError


class Signer(Protocol):
    def headers(self, *, query: str, body: bytes, config: SDKConfig) -> dict[str, str]: ...


class HttpTransport:
    def __init__(self, config: SDKConfig, *, signer: Signer | None = None, client: httpx.Client | None = None):
        self.config = config
        self.signer = signer
        self.client = client or httpx.Client(timeout=config.timeout)

    def post(self, path: str, *, params: list[tuple[str, str]], json_body: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
        return self._send("POST", path, params=params, json_body=json_body, base_url=base_url)

    def get(self, path: str, *, params: list[tuple[str, str]], base_url: str | None = None) -> dict[str, Any]:
        return self._send("GET", path, params=params, json_body=None, base_url=base_url)

    def _send(self, method: str, path: str, *, params: list[tuple[str, str]], json_body: dict[str, Any] | None, base_url: str | None) -> dict[str, Any]:
        request = self.client.build_request(method, (base_url or self.config.base_url) + path, params=params, json=json_body) if json_body is not None else self.client.build_request(method, (base_url or self.config.base_url) + path, params=params)
        if self.signer:
            body = request.content or b""
            query = request.url.query.decode("utf-8")
            request.headers.update(self.signer.headers(query=query, body=body, config=self.config))
        response = self.client.send(request)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError("CapCut returned a non-JSON response", status_code=response.status_code) from exc
        ret = payload.get("ret", "0")
        ret_failed = isinstance(ret, (str, int)) and str(ret) not in {"0", ""}
        if response.status_code >= 400 or ret_failed:
            raise ApiError(payload.get("errmsg") or "CapCut API request failed", status_code=response.status_code, payload=payload)
        return payload
