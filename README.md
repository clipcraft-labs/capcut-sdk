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

## Quick start

The first command creates a local `default` profile automatically:

```bash
capcut effects search 'blur'
```

The default profile is created with generated local identifiers and `live`
mode, so supported catalog endpoints can be queried immediately.

To replace the generated identifiers later:

```bash
capcut auth profile set default \
  --device-id 'your-device-id' \
  --iid 'your-install-id' \
  --region KR \
  --language ko-KR \
  --mode live
```

Profiles are stored locally at:

```text
~/.config/clipcraft-labs/capcut/profiles/default.toml
```

Generated identifiers work for catalog endpoints; login-required endpoints may
still return an authentication error.

## Supported API operations

The SDK currently exposes these operation groups:

- Effects: list by category, search, search words, panel information
- Music: collections, music-effect collections, and collection songs
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
capcut music collections
capcut music songs <collection-id>
capcut templates collections
capcut templates list <collection-id> --cursor 0
capcut call /artist/v1/effect/search request.json
```

All paginated clients expose page metadata such as `has_more`, `next_offset`,
and `next_cursor`. Use `iter_pages`, `iter_songs`, or `iter` when you want to
walk every page.

## Python

```python
from capcut_sdk import CapCutClient, CapCutSigner, ProfileStore

config = ProfileStore().sdk_config("default")
client = CapCutClient(config, signer=CapCutSigner())
page = client.effects.search("blur")
```

The built-in `CapCutSigner` is included in the SDK.

This is an unofficial, observation-based API. Availability and response
schemas can change. Review applicable terms of service and laws before use.
