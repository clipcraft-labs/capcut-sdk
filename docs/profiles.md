# Local profiles

The CLI creates `default` automatically on first profile access. Profiles are
TOML files stored outside the repository:

```text
~/.config/clipcraft-labs/capcut/profiles/default.toml
```

The default profile uses synthetic device and install identifiers and starts
in `offline` mode. It is safe for inspecting the CLI and running local tests;
it must not be used for live CapCut requests.

```bash
capcut auth profile list
capcut auth profile show
capcut auth profile set default --region KR --language ko-KR
```

Environment variables override a profile for one process:

```bash
CAPCUT_MODE=live \
CAPCUT_DEVICE_ID='your-device-id' \
CAPCUT_IID='your-install-id' \
capcut effects search 'blur'
```

The profile directory is created with mode `0700` and profile files with mode
`0600`. Identifiers are masked by `profile show`. The SDK never discovers or
extracts real account credentials from captures.

The same configuration root contains a `cache/` directory for local JSON
responses. `JsonCache` and `RecordIndex` provide local extraction and search
primitives without sending data to a third-party service.
