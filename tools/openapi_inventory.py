#!/usr/bin/env python3
"""Emit deterministic operation scaffolding from the OpenAPI spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

STABLE = {"getResourcesByCategoryId", "getPanelInfo", "searchEffects", "getEffectSearchWords", "getMusicCollections", "getMusicEffectCollections", "getCollectionSongs", "getTemplateCollections", "getCollectionTemplates", "getRandomAigcPrompts"}


def inventory(spec_path: Path) -> list[dict[str, str]]:
    document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    result = []
    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if operation_id:
                result.append({"operation_id": operation_id, "method": method.upper(), "path": path, "group": str((operation.get("tags") or ["default"])[0]).lower(), "status": "stable" if operation_id in STABLE else "scaffold"})
    return sorted(result, key=lambda item: item["operation_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, nargs="?", default=Path("openapi.yaml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(inventory(args.spec), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
