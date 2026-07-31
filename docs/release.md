# Release process

This project is an unofficial, capture-backed SDK. Releases are made only
from a clean public clone; local captures and runtime responses must not be
part of the commit.

## Before the first public commit

```bash
make test
python tools/public_audit.py .
python tools/openapi_inventory.py openapi.yaml
```

Review `docs/public-release-checklist.md` manually. In particular, inspect
the complete diff for device identifiers, cookies, signed URLs, account IDs,
and response payloads copied from a live session.

## Versioning

The package follows semantic versioning while the API is experimental:

- `0.x` may change SDK method signatures as capture evidence improves.
- A stable operation means its request shape, response mapping, and tests are
  backed by sanitized fixtures; it does not imply an official CapCut contract.
- Breaking changes are recorded in `CHANGELOG.md`.

