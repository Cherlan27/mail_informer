.PHONY: check test specs

# The project check: must pass at the end of apply and fixes, and runs in CI.
check: test specs

test:
	@test -n "$$TEST_DATABASE_URL" || { echo "TEST_DATABASE_URL is not set, so the Postgres tests would be skipped. See CONTRIBUTING.md."; exit 1; }
	python -m pytest -q

specs:
	openspec validate --all --strict
