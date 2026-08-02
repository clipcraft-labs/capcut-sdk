# CapCut API SDK

Unofficial Python SDK and CLI for exploring the CapCut Desktop API surface.

## Install

```bash
python -m pip install git+https://github.com/clipcraft-labs/capcut-sdk.git
```

For local development:

```bash
python -m pip install -e .
```

## Documentation

- [API Reference](https://clipcraft-labs.docs.buildwithfern.com)
- [Source repository](https://github.com/clipcraft-labs/capcut-sdk)
- [Draft compiler](https://github.com/clipcraft-labs/capcut-draft)
- [Unified Clipcraft CLI](https://github.com/clipcraft-labs/clipcraft-cli)

The documentation includes the complete
[exact resource-ID workflow](https://clipcraft-labs.docs.buildwithfern.com/guides/get-started/resolve-exact-resource-i-ds),
[Project JSON pipeline](https://clipcraft-labs.docs.buildwithfern.com/guides/get-started/build-your-first-project),
[headless runner contract](https://clipcraft-labs.docs.buildwithfern.com/guides/build-projects/headless-rendering),
and [public repository safety rules](https://clipcraft-labs.docs.buildwithfern.com/guides/safety/privacy-and-public-repositories).

## Quick start

The first command creates a local `default` profile automatically:

```bash
capcut effects search 'blur'
```

The default profile is created with generated local identifiers and `live`
mode, so supported catalog endpoints can be queried immediately.

## Profiles

Profiles are stored locally at:

```text
~/.config/clipcraft-labs/capcut/profiles/default.toml
```

Inspect the active profile:

```bash
capcut auth profile list
capcut auth profile show
```

To replace the generated identifiers later:

```bash
capcut auth profile set default \
  --device-id 'your-device-id' \
  --iid 'your-install-id' \
  --region KR \
  --language ko-KR \
  --mode live
```

Generated identifiers work for catalog endpoints; login-required endpoints may
still return an authentication error.

## Supported API operations

The SDK currently exposes these operation groups:

- Effects: list by category, search, search words, panel information
- Music: collections, sound-effect collections, collection songs, and local preview downloads
- Templates: collections and cursor-paginated template items
- AIGC: random prompts
- Configuration: effect settings, remote settings, model metadata, monitor
  settings, benefits, and compliance responses
- Raw API: call any documented GET or POST operation through the OpenAPI
  contract

## CLI examples

```bash
capcut effects search 'blur'
capcut panels info --panel effects2
capcut panels info --panel transitions --format catalog
capcut effects list --panel transitions --category-id <id> --format catalog
capcut music collections
capcut music collections --effects
capcut music songs <collection-id> --limit 10 --download-dir ./downloads
capcut templates collections
capcut templates list <collection-id> --cursor 0
capcut call /artist/v1/effect/search request.json
```

All paginated clients expose page metadata such as `has_more`, `next_offset`,
and `next_cursor`. Use `iter_pages`, `iter_songs`, or `iter` when you want to
walk every page.

`music songs --download-dir` downloads each returned `preview_url` locally and
stores ISO-BMFF/AAC previews as `.m4a` when the server response identifies that
format. Downloaded previews remain local and should not be committed.

Use `--format catalog` when another SDK, draft compiler, MCP server, or Skill
needs stable records instead of version-dependent raw API responses. Catalogue
records normalize provider, resource kind, identifiers, display name, category,
VIP/commercial flags, preview URL, and duration while leaving raw output as the
backward-compatible default.

## Python

```python
from capcut_sdk import CapCutClient, CapCutSigner, ProfileStore

config = ProfileStore().sdk_config("default")
client = CapCutClient(config, signer=CapCutSigner())
page = client.effects.search("blur")
```

The built-in `CapCutSigner` is included in the SDK.

## Public package boundary

This repository does not distribute CapCut, VEHelper, dynamic libraries,
catalogue bundles, music, models, fonts, raw captures, cookies, account state,
or real device identifiers. Exact-ID resolution may read the installed Desktop
Resource SDK HTTP cache in read-only mode; it does not require CapCut to be
running and does not copy the database into project output.

Working lockfiles and response dumps are private by default because they can
contain expiring signed URLs or account/region-specific metadata. Use synthetic
fixtures and sanitized lock records in public repositories.

This is an unofficial, observation-based API. Availability and response
schemas can change. Review applicable terms of service and laws before use.
