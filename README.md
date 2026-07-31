# CapCut Unofficial OpenAPI

> Unofficial research SDK and CLI for capture-backed CapCut API operations.

The public home for this SDK is `clipcraft-labs/capcut-sdk`. Research inputs
and native runtime experiments live in the separate
`clipcraft-labs/capcut-research` repository.

The repository is being migrated from a reverse-engineering workspace into an
installable Python SDK. OpenAPI is the contract, the SDK contains typed/domain
clients, and the CLI is a thin interface over the SDK. Only operations with
sufficient capture evidence are marked stable; other operations remain
experimental or scaffold-only.

## Install the SDK

```bash
python -m pip install -e .
capcut api status
python -m capcut_sdk api status
```

Live commands use caller-provided identifiers and the built-in CapCut signer:

```bash
export CAPCUT_DEVICE_ID='your-device-id'
export CAPCUT_IID='your-install-id'
capcut effects search 'blur'
capcut panels info --panel effects2
capcut music collections
capcut music songs <collection-id>
capcut templates collections
capcut templates list <collection-id> --cursor 0
capcut call /artist/v1/effect/search request.json
```

`capcut call` is the compatibility path for OpenAPI operations that do not yet
have a typed resource adapter. It still uses the configured transport and
signer.

Do not put these values in shell history, fixtures, or source control.

Signing is injected through a transport boundary so credentials, device
profiles, and future signer implementations remain outside endpoint clients.
The bundled `CapCutSigner` provides the currently verified pure-Python signing
implementation without requiring the research repository.

## OpenAPI scaffolding

The repository keeps the OpenAPI document as the API contract. The first
converter stage produces deterministic operation metadata and deliberately
does not guess domain semantics:

```bash
python tools/openapi_inventory.py openapi.yaml
```

Hand-written adapters promote verified operations from `scaffold` to
`stable`; this keeps generated code from hiding capture or signing gaps.

Raw capture files and harness runtime responses are local-only inputs. To
prepare a candidate public JSON fixture, use:

```bash
python tools/sanitize_fixture.py private-response.json fixtures/example.json
```

The output still requires manual review before publication.

This repository documents an unofficial OpenAPI 3.1 surface observed from
CapCut Desktop network traffic.

- Specification: [`openapi.yaml`](./openapi.yaml)
- Raw captures: retained privately in `capcut-research/private/captures/`
- Observation date: 2026-07-31
- Observed region: Singapore (`*-sg.capcutapi.com`)

## Scope

The document covers 23 CapCut API operations observed in local research.

- Effects, stickers, filters, transitions, captions, and material panels
- Material search, suggested terms, and batch lookups
- Music collections and songs
- Template collections, items, and batch lookups
- AIGC prompts and user-generated lists
- Models, remote settings, benefits, and compliance
- Application telemetry

Image, video, and model CDN requests are static asset delivery rather than
API operations and are excluded.

## Pagination

### Materials, search, and music

When `has_more` is `true`, use `next_offset` as the next request's `offset`.

Do not infer completion from array length; `has_more` can remain true even when
fewer than `count` items are returned.

### Templates

When `has_more` is `true`, use `new_cursor` as the next request's `cursor`.
Observed cursors included `0 → 12 → 24 → 36`.

## Authentication and signing

These are not public APIs. The application uses signing and device headers such
as `sign`, `X-Gorgon`, `X-Khronos`, `X-Argus`, `X-Ladon`, `X-SS-DP`,
`X-SS-STUB`, and `TDID`.

The specification records header names only; it contains no captured tokens,
cookies, device identifiers, or signature values. Signing implementation is
outside this document's scope.

See the [`capcut-research` harness](https://github.com/clipcraft-labs/capcut-research)
for native runtime experiments. See the
[`pure-python-signer` research notes](https://github.com/clipcraft-labs/capcut-research/tree/main/signing/pure-python-signer)
behind the built-in signer.

## Notes

- This is an observation-based, unofficial specification; fields may change.
- Confirmed fields are modeled explicitly; sparse or dynamic areas retain
  `additionalProperties: true`.
- Host names can vary by region.
- Review applicable terms of service and laws before use.
