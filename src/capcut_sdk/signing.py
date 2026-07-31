"""Built-in CapCut request signer.

The SDK ships the verified pure-Python signing primitives in
``capcut_sdk.auth``. Research notes and native tracing tools live in the
separate ``capcut-research`` repository.
"""

import time

from .config import SDKConfig
from .errors import ConfigurationError

try:
    from .auth import x_argus, x_gorgon, x_khronos, x_ladon, x_ss_stub
except ImportError as exc:  # pragma: no cover - exercised by packaging checks
    x_argus = x_gorgon = x_khronos = x_ladon = x_ss_stub = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class CapCutSigner:
    """Generate headers required by the observed CapCut desktop client."""

    def headers(self, *, query: str, body: bytes, config: SDKConfig) -> dict[str, str]:
        if _IMPORT_ERROR is not None:
            raise ConfigurationError(
                "Built-in CapCut signing support is unavailable"
            ) from _IMPORT_ERROR
        timestamp = int(time.time())
        stub = x_ss_stub(body)
        return {
            "X-Khronos": x_khronos(timestamp),
            "X-SS-STUB": stub,
            "X-Gorgon": x_gorgon(query, body, "", timestamp, stub=stub),
            "X-Ladon": x_ladon(timestamp, app_id=config.app_id),
            "X-Argus": x_argus(query, body, timestamp, app_id=config.app_id, device_id=config.device.device_id, stub=stub),
            "X-SS-DP": str(config.app_id),
            "TDID": config.device.device_id,
        }
