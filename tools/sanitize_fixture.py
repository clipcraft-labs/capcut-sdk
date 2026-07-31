#!/usr/bin/env python3
"""Sanitise a JSON response before it becomes a public SDK fixture.

This tool is intentionally conservative. It removes identifiers, cookies,
signed URLs, and opaque signatures while retaining response shape and useful
domain fields. It never modifies the input file in place.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = re.compile(r"(?:^|_)(?:device|iid|install|cookie|token|authorization|signature|sign|uid|user_id|logid|request_id|trace|tdid)(?:$|_)", re.I)
SENSITIVE_QUERY = {"x-signature", "x-expires", "signature", "token", "access_token", "odin_tt"}


def sanitize(value, *, key: str = ""):
    if isinstance(value, dict):
        return {name: "<redacted>" if SENSITIVE_KEYS.search(name) else sanitize(item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item, key=key) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        query = [(name, "<redacted>" if name.lower() in SENSITIVE_QUERY else item) for name, item in parse_qsl(parsed.query, keep_blank_values=True)]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(sanitize(source), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

