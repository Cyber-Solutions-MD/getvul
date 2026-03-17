.PHONY: help dev down migrate test lint fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start all services (Postgres, Redis, backend, frontend)
	docker compose up --build

dev-d: ## Start all services in background
	docker compose up --build -d

down: ## Stop all services
	docker compose down

down-v: ## Stop all services and remove volumes (fresh DB)
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

migrate: ## Run all pending migrations
	docker compose exec backend alembic upgrade head

migrate-down: ## Rollback last migration
	docker compose exec backend alembic downgrade -1

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add xyz")
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

db-shell: ## Open psql shell
	docker compose exec postgres psql -U getvul -d getvul

backend-shell: ## Open a shell in the backend container
	docker compose exec backend bash

test: ## Run backend tests
	docker compose exec backend pytest -v --cov=app --cov-report=term-missing

test-local: ## Run backend tests locally (requires local venv)
	cd backend && pytest -v --cov=app --cov-report=term-missing

lint: ## Lint backend code
	cd backend && ruff check .

fmt: ## Format backend code
	cd backend && ruff format .

typecheck: ## Run mypy type checks
	cd backend && mypy app/

fe-install: ## Install frontend dependencies
	cd frontend && npm install

fe-dev: ## Run frontend dev server locally
	cd frontend && npm run dev

fe-lint: ## Lint frontend code
	cd frontend && npm run lint

fe-build: ## Build frontend for production
	cd frontend && npm run build

tf-init: ## Initialize Terraform
	cd infra && terraform init

tf-plan: ## Plan Terraform changes
	cd infra && terraform plan

tf-apply: ## Apply Terraform changes
	cd infra && terraform apply

tf-destroy: ## Destroy Terraform resources (DANGER)
	cd infra && terraform destroy
