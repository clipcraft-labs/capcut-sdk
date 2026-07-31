# Organization and repository plan

The public GitHub organization is `clipcraft-labs`.

Repositories are intentionally separated by responsibility:

- `capcut-sdk` — installable Python SDK, CLI, OpenAPI contract, and reviewed
  synthetic fixtures.
- `capcut-research` — native runtime experiments, reverse-engineering notes,
  and local-only captures.

This separation keeps account data, device identifiers, response dumps, and
compiled research artifacts outside the SDK repository. Future MCP or video
production projects can use their own repositories without coupling them to
the SDK release cycle.

## Naming rules

- Organization: `clipcraft-labs`
- SDK repository: `capcut-sdk`
- Research repository: `capcut-research`
- Python distribution: `capcut-api-sdk`
- Python import: `capcut_sdk`
- CLI command: `capcut`
