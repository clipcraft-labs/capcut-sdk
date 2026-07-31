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

After receiving real identifiers, configure the default profile once:

```bash
capcut auth profile set default \
  --device-id 'your-device-id' \
  --iid 'your-install-id' \
  --mode live
capcut effects search 'blur'
```

The CLI uses the default profile automatically; no `export` commands are
required. Environment variables remain an optional one-process override for
automation and are not part of the normal setup.

The profile directory is created with mode `0700` and profile files with mode
`0600`. Identifiers are masked by `profile show`. The SDK never discovers or
extracts real account credentials from captures.

The same configuration root contains a `cache/` directory for local JSON
responses. `JsonCache` and `RecordIndex` provide local extraction and search
primitives without sending data to a third-party service.
