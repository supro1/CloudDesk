ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
else
PYTHON ?= .venv/bin/python
endif

HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help setup backend demo ingest test lint terraform-validate

help:
	@echo "setup   Sync dependencies and create .env from .env.example if absent"
	@echo "backend Run the FastAPI development server"
	@echo "demo    Run the approval or security escalation demo (TICKET=CD-1002|CD-1005)"
	@echo "ingest  Load and index the knowledge-base Markdown articles"
	@echo "test    Run the offline test suite"
	@echo "lint    Run Ruff on backend and tests"
	@echo "terraform-validate Format and validate the AWS, Azure, and GCP Terraform roots"

setup:
	uv sync --group dev
	$(PYTHON) -c "from pathlib import Path; import shutil; source = Path('.env.example'); target = Path('.env'); shutil.copyfile(source, target) if not target.exists() else None"

backend:
	$(PYTHON) -m uvicorn backend.app.main:app --reload --host $(HOST) --port $(PORT)

demo:
	$(PYTHON) -m scripts.demo --ticket $(if $(TICKET),$(TICKET),CD-1002)

ingest:
	$(PYTHON) -m rag.ingest

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check --isolated --select E4,E7,E9,F backend tests

terraform-validate:
	terraform fmt -check -recursive deployment
	terraform -chdir=deployment/aws init -backend=false -input=false
	terraform -chdir=deployment/aws validate
	terraform -chdir=deployment/azure init -backend=false -input=false
	terraform -chdir=deployment/azure validate
	terraform -chdir=deployment/gcp init -backend=false -input=false
	terraform -chdir=deployment/gcp validate
