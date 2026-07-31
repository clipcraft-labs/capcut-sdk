"""Explicit, serialisable SDK configuration.

Credentials and device identifiers are deliberately supplied by the caller;
the SDK never reads them from captures or commits them to the repository.
"""

from dataclasses import dataclass

from .auth import CAPCUT_APP_ID


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    device_id: str
    iid: str
    device_brand: str = "Mac15,9"
    device_platform: str = "mac"
    device_type: str = "arm64"
    os_version: str = ""
    cpu: str = ""
    gpu: str = ""


@dataclass(frozen=True, slots=True)
class SDKConfig:
    device: DeviceProfile
    region: str = "KR"
    language: str = "ko-KR"
    app_id: int = CAPCUT_APP_ID
    app_name: str = "CapCut"
    version_name: str = "9.1.0"
    version_code: str = "9.1.0"
    effect_sdk_version: str = "21.8.0"
    service: str = "heycan-api-sg"
    editor_service: str = "editor-api-sg"
    timeout: float = 30.0
    mode: str = "offline"

    @property
    def base_url(self) -> str:
        return f"https://{self.service}.capcutapi.com"

    @property
    def editor_base_url(self) -> str:
        return f"https://{self.editor_service}.capcutapi.com"
