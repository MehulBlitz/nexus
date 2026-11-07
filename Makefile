.PHONY: backend-install backend-test backend-lint backend-format frontend-install frontend-build frontend-check up down

backend-install:
	cd backend && pip install -e ".[dev]" --break-system-packages
backend-test:
	cd backend && pytest -q
backend-lint:
	cd backend && ruff check . && ruff format --check .
backend-format:
	cd backend && ruff format . && ruff check --fix .
frontend-install:
	cd frontend && npm install
frontend-check:
	cd frontend && npm run typecheck && npm run lint
frontend-build:
	cd frontend && npm run build
up:
	docker compose up --build
down:
	docker compose down
