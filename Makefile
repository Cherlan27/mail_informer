.PHONY: check test specs

# The project check: must pass at the end of apply and fixes, and runs in CI.
check: test specs

test:
	python -m pytest -q

specs:
	openspec validate --all --strict
