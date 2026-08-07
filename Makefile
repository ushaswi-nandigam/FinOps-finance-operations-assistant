.PHONY: up down migrate seed load-seed test eval demo lint format help

help:
	@echo "Agentic FinOps Assistant — Available Commands:"
	@echo "  make up        - Spin up Docker Compose services (MySQL, API, Web)"
	@echo "  make down      - Shut down Docker Compose services"
	@echo "  make migrate   - Apply db/schema.sql to DATABASE_URL"
	@echo "  make seed      - Generate coherent synthetic data across CRM, Payments, Fraud, KB"
	@echo "  make load-seed - Load generated data/generated/*.json into MySQL"
	@echo "  make test      - Run pytest suite with coverage"
	@echo "  make eval      - Run golden evaluation set and produce metrics report"
	@echo "  make demo      - Run golden path demo driver scenarios"
	@echo "  make lint      - Run ruff & mypy checks"

up:
	docker compose up -d

down:
	docker compose down

migrate:
	python scripts/migrate.py

seed:
	python scripts/seed.py

load-seed:
	python scripts/load_seed.py

index-policies:
	python scripts/index_policies.py

test:
	pytest tests/ --cov=services --cov-report=term-missing

golden-set:
	python evals/generate_golden_set.py

eval:
	python evals/runner.py

demo:
	python scripts/demo_driver.py

lint:
	ruff check .
	mypy services
