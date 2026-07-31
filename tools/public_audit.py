#!/usr/bin/env python3
"""Fail when likely secrets or private capture artifacts enter public files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PRIVATE_DIRS = {"captures", "harness/runtime", ".git", ".venv", "build", "dist", "generated"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".json", ".txt", ".cfg", ".ini"}
PATTERNS = (
    re.compile(r"\b(?:Authorization|Cookie)\s*:\s*\S+"),
    re.compile(r"(?i)\b(?:x-argus|x-ladon)\s*:\s*[A-Za-z0-9+/=]{32,}"),
    re.compile(r"(?i)\b(?:x-gorgon)\s*:\s*[0-9a-f]{32,}"),
    re.compile(r"(?i)\b(?:odin_tt|access_token|api[_-]?key)\s*[=:]\s*[^\s<]"),
)


def is_private(path: Path) -> bool:
    parts = path.as_posix().split("/")
    return any("/".join(parts[:i]) in PRIVATE_DIRS or part in PRIVATE_DIRS for i, part in enumerate(parts, 1))


def audit(root: Path) -> list[str]:
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or is_private(path) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{path}:{number}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    findings = audit(args.root)
    if findings:
        print("Public audit failed:")
        print("\n".join(findings))
        return 1
    print("Public audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
