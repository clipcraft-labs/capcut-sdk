.PHONY: test test-sdk inventory audit compile

test: test-sdk inventory audit compile

test-sdk:
	PYTHONPATH=src:. python3 -m unittest discover -s tests -v

inventory:
	PYTHONPATH=src:. python3 tools/openapi_inventory.py openapi.yaml >/tmp/capcut-openapi-inventory.json

audit:
	python3 tools/public_audit.py .

compile:
	python3 -m compileall -q src tools tests
