PYTHON  = python3.12
VENV    = .venv
BIN     = $(VENV)/bin

.PHONY: install db migrate dev seed benchmark reset demo

# ── One-time setup ────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -r requirements.txt
	@echo "Done. Run: make db && make migrate && make dev"

# ── Runtime services ──────────────────────────────────────────────────────────

db:
	docker compose up -d
	@echo "Postgres running on :5432"

migrate:
	$(BIN)/alembic upgrade head
	@echo "Migrations applied"

dev:
	$(BIN)/uvicorn app.main:app --reload

# ── Demo helpers ──────────────────────────────────────────────────────────────

# Load the fixture PDF (Attention Is All You Need) from a clean state.
# Requires the server to NOT be running — seed runs the pipeline directly.
demo: reset seed
	@echo ""
	@echo "Demo ready. Open: http://localhost:8000"
	@echo "Sample questions:"
	@echo "  - What is the Transformer model?"
	@echo "  - How does multi-head attention work?"
	@echo "  - What BLEU score did the model achieve?"

reset:
	$(BIN)/python scripts/reset.py

seed:
	$(BIN)/python scripts/seed_sample.py

# ── Utilities ─────────────────────────────────────────────────────────────────

benchmark:
	$(BIN)/python scripts/benchmark.py
