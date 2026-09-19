.PHONY: help setup backend frontend db test lint fmt check clean

help:
	@echo "make setup     - create venv + install backend and frontend deps"
	@echo "make db        - start PostgreSQL in Docker"
	@echo "make backend   - run FastAPI on :8000 (reload)"
	@echo "make frontend  - run Next.js on :3000"
	@echo "make test      - run backend tests"
	@echo "make lint      - ruff check"
	@echo "make fmt       - ruff format"
	@echo "make check     - lint + test (run this before every push)"

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install
	@test -f .env || cp .env.example .env
	@echo "Setup done. Edit .env, then: make db && make backend"

db:
	docker compose up -d postgres

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check app tests

fmt:
	cd backend && .venv/bin/ruff format app tests

check: lint test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache
