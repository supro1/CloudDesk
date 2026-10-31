ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
else
PYTHON ?= .venv/bin/python
endif

HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help setup backend demo test lint

help:
	@echo "setup   Sync dependencies and create .env from .env.example if absent"
	@echo "backend Run the FastAPI development server"
	@echo "demo    Start the backend; demo fixtures load on startup when DEMO_MODE=true"
	@echo "test    Run the offline test suite"
	@echo "lint    Run Ruff on backend and tests"

setup:
	uv sync --group dev
	$(PYTHON) -c "from pathlib import Path; import shutil; source = Path('.env.example'); target = Path('.env'); shutil.copyfile(source, target) if not target.exists() else None"

backend:
	$(PYTHON) -m uvicorn backend.app.main:app --reload --host $(HOST) --port $(PORT)

demo:
	@echo "Demo fixtures load on startup when DEMO_MODE=true; workflow components are not ready yet."
	@$(MAKE) backend

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check --isolated --select E4,E7,E9,F backend tests
