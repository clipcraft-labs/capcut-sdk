.PHONY: test test-sdk test-method2 inventory audit compile

test: test-sdk test-method2 inventory audit compile

test-sdk:
	PYTHONPATH=src:method2:. python3 -m unittest discover -s tests -v

test-method2:
	PYTHONPATH=src:method2:. python3 -m unittest discover -s method2/tests -v

inventory:
	PYTHONPATH=src:method2:. python3 tools/openapi_inventory.py openapi.yaml >/tmp/capcut-openapi-inventory.json

audit:
	python3 tools/public_audit.py .

compile:
	python3 -m compileall -q src tools tests
