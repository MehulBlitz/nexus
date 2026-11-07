.PHONY: backend-install backend-test backend-lint backend-migrate frontend-install frontend-test frontend-check frontend-build mcp-install mcp-test mcp-lint check worker mcp-run up down

backend-install:
	cd backend && pip install -e ".[dev]"
backend-test:
	cd backend && pytest -q
backend-lint:
	cd backend && ruff check .
backend-migrate:
	cd backend && python -m alembic upgrade head

frontend-install:
	cd frontend && npm install
frontend-test:
	cd frontend && npm test
frontend-check:
	cd frontend && npm run typecheck && npm run lint
frontend-build:
	cd frontend && npm run build

mcp-install:
	cd mcp-server && pip install -e ".[dev]"
mcp-test:
	cd mcp-server && PYTHONPATH=. pytest -q
mcp-lint:
	cd mcp-server && ruff check .

check: backend-lint backend-test frontend-check frontend-test frontend-build mcp-lint mcp-test

worker:
	cd backend && python -m app.workers.runner

mcp-run:
	cd mcp-server && python -m nexus_mcp.server

up:
	docker compose up --build
down:
	docker compose down
