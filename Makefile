.PHONY: run test install venv clean seed backfill

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
PY := $(BIN)/python
PIP := $(BIN)/pip
PYTEST := $(BIN)/pytest

# Use venv if it exists
ifeq ($(wildcard $(VENV)),)
	RUN_PY := $(PYTHON)
	RUN_PIP := $(PYTHON) -m pip
	RUN_PYTEST := $(PYTHON) -m pytest
else
	RUN_PY := $(PY)
	RUN_PIP := $(PIP)
	RUN_PYTEST := $(PYTEST)
endif

run:
	$(RUN_PY) run.py

test:
	$(RUN_PYTEST) tests/ -v --tb=short

test-cov:
	$(RUN_PIP) install pytest-cov -q 2>/dev/null || true
	$(RUN_PYTEST) tests/ -v --tb=short --cov=src --cov-report=term-missing

install: venv
	$(PIP) install -r requirements.txt

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

seed:
	$(RUN_PY) scripts/seed_faq.py data/faq_seed.json

backfill:
	$(RUN_PY) scripts/backfill.py

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
