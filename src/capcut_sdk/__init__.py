"""Public Python SDK for the capture-backed CapCut API."""

from .client import CapCutClient
from .config import DeviceProfile, SDKConfig
from .errors import ApiError, ConfigurationError
from .signing import CapCutSigner
from .profiles import ProfileStore, config_from_environment
from .cache import JsonCache
from .search import RecordIndex
from .catalog import EFFECT_TYPE_KINDS, PANEL_KINDS, CatalogCategory, CatalogResource, infer_effect_kind
from .desktop_cache import DesktopCacheCatalog, default_ressdk_roots

__version__ = "0.2.0"

__all__ = ["ApiError", "CapCutClient", "CapCutSigner", "CatalogCategory", "CatalogResource", "ConfigurationError", "DesktopCacheCatalog", "DeviceProfile", "EFFECT_TYPE_KINDS", "JsonCache", "PANEL_KINDS", "ProfileStore", "RecordIndex", "SDKConfig", "config_from_environment", "default_ressdk_roots", "infer_effect_kind", "__version__"]
