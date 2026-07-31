# Contributing

Contributions should be based on sanitised captures or synthetic fixtures.

For a newly observed operation:

1. Update `openapi.yaml` with only observed fields.
2. Add a redacted fixture and a focused model/client test.
3. Keep signing and device configuration outside captured data.
4. Mark the operation stable only after a live or replay test succeeds.

Run the test suite with:

```bash
python -m pip install -e '.[dev]'
make test
```

The raw capture and harness runtime directories are research inputs, not
public fixtures. Before opening a pull request, use synthetic or sanitised
fixtures and run the public-release checklist.
