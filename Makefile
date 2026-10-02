.PHONY: check test

check: test

test:
	python3 -m pytest tests/ -v
