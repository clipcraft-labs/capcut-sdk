"""Method 2 signer adapter.

The cryptographic implementation remains in the research-compatible
``capcut_method2`` package for now. This adapter is the stable SDK boundary;
it can be replaced by a vendored implementation without changing clients.
"""

import time

from .config import SDKConfig
from .errors import ConfigurationError

try:
    from capcut_method2 import x_argus, x_gorgon, x_khronos, x_ladon, x_ss_stub
except ImportError as exc:  # pragma: no cover - exercised by packaging checks
    x_argus = x_gorgon = x_khronos = x_ladon = x_ss_stub = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class Method2Signer:
    """Generate the headers required by the observed CapCut desktop client."""

    def headers(self, *, query: str, body: bytes, config: SDKConfig) -> dict[str, str]:
        if _IMPORT_ERROR is not None:
            raise ConfigurationError(
                "Method 2 support is unavailable; install the bundled capcut_method2 package"
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

