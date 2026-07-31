"""Operation inventory derived from the checked-in OpenAPI document.

This registry is intentionally explicit: it gives the CLI and documentation a
stable view while endpoint adapters are implemented incrementally.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    group: str
    status: str


OPERATIONS = (
    Operation("getResourcesByCategoryId", "materials", "stable"),
    Operation("getPanelInfo", "materials", "stable"),
    Operation("searchEffects", "search", "stable"),
    Operation("getEffectSearchWords", "search", "stable"),
    Operation("multiGetArtistItems", "materials", "scaffold"),
    Operation("multiGetItems", "materials", "scaffold"),
    Operation("getEffectGeneralConfig", "configuration", "scaffold"),
    Operation("listEffectsByResourceId", "materials", "scaffold"),
    Operation("getUserAigcList", "aigc", "auth-required"),
    Operation("getRandomAigcPrompts", "aigc", "stable"),
    Operation("getMusicCollections", "music", "stable"),
    Operation("getMusicEffectCollections", "music", "stable"),
    Operation("getCollectionSongs", "music", "stable"),
    Operation("getTemplateCollections", "templates", "stable"),
    Operation("getCollectionTemplates", "templates", "stable"),
    Operation("multiGetTemplates", "templates", "scaffold"),
    Operation("getModelArithmetics", "configuration", "scaffold"),
    Operation("getRemoteSettings", "configuration", "scaffold"),
    Operation("getMonitorSettings", "configuration", "scaffold"),
    Operation("batchGetUserBenefit", "configuration", "auth-required"),
    Operation("fetchCompliancePopups", "configuration", "scaffold"),
    Operation("ingestEventBatches", "telemetry", "experimental"),
    Operation("ingestEvents", "telemetry", "experimental"),
)
