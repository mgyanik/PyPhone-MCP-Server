.PHONY: check test

# pytest 安装在该解释器下；可用 make PYTHON=python3 覆盖
PYTHON ?= python3.14

check: test

test:
	$(PYTHON) -m pytest tests/ -v
