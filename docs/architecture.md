# Architecture

The repository has four deliberately separate layers:

```text
openapi.yaml                 observed API contract
        |
tools/openapi_inventory.py   deterministic converter/scaffold metadata
        |
src/capcut_sdk/              public Python SDK, CLI, and built-in signer
        |
capcut-research/signing/     separate native analysis and research evidence
```

The SDK transport accepts a signer through a protocol. The default
`CapCutSigner` is bundled in the SDK, while native analysis and research
evidence remain in the separate research repository.

## Promotion workflow

New endpoints start as `scaffold` in the operation registry. A captured request
and a sanitised response fixture are required before adding a domain adapter.
The adapter is then tested with a mock transport and promoted to `stable`.

## Public repository boundary

The public repository may contain OpenAPI schemas, synthetic vectors,
sanitised fixtures, and documentation. It must not contain raw MITM captures,
cookies, device/install identifiers, account identifiers, access tokens, or
live request signatures. Raw captures remain local research inputs.
