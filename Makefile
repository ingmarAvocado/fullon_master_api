# Fullon Master API - Development Makefile

.PHONY: help install test lint format run clean setup dev-setup

# Default target
help:
	@echo "Fullon Master API - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup        - Initial project setup (install + .env)"
	@echo "  make install      - Install dependencies with Poetry"
	@echo "  make dev-setup    - Setup development environment"
	@echo ""
	@echo "Development:"
	@echo "  make run          - Run development server"
	@echo "  make test         - Run test suite"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Run linters (ruff + mypy)"
	@echo "  make format       - Format code (black + ruff)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Clean generated files"
	@echo "  make update       - Update dependencies"

# Setup commands
setup: install
	@if [ ! -f .env ]; then \
		echo "Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo "✅ .env created - Please update with your credentials"; \
	else \
		echo "✅ .env already exists"; \
	fi

install:
	@echo "Installing dependencies with Poetry..."
	poetry install
	@echo "✅ Dependencies installed"

dev-setup: setup
	@echo "Setting up pre-commit hooks..."
	poetry run pre-commit install
	@echo "✅ Development environment ready"

# Development commands
run:
	@echo "Starting Fullon Master API..."
	poetry run uvicorn fullon_master_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	@echo "Running test suite..."
	poetry run pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	poetry run pytest tests/ -v --cov=fullon_master_api --cov-report=html --cov-report=term
	@echo "✅ Coverage report generated in htmlcov/index.html"

test-watch:
	@echo "Running tests in watch mode..."
	poetry run pytest-watch tests/ -v

# Code quality
lint:
	@echo "Running linters..."
	poetry run ruff check src/ tests/
	poetry run mypy src/

format:
	@echo "Formatting code..."
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/
	@echo "✅ Code formatted"

# Maintenance
clean:
	@echo "Cleaning generated files..."
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

update:
	@echo "Updating dependencies..."
	poetry update
	@echo "✅ Dependencies updated"

# Docker commands (for future use)
docker-build:
	@echo "Building Docker image..."
	docker build -t fullon-master-api:latest .

docker-run:
	@echo "Running Docker container..."
	docker run -p 8000:8000 --env-file .env fullon-master-api:latest
