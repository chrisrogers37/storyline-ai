.PHONY: help install test clean create-db drop-db reset-db init-db setup-db check-health run dev

# Load environment variables from .env file
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Default environment file
ENV_FILE ?= .env

# Database connection variables
DB_HOST ?= localhost
DB_PORT ?= 5432
DB_NAME ?= storyline_ai
DB_USER ?= postgres
DB_PASSWORD ?=

# PostgreSQL connection string for admin operations (connects to postgres database)
ADMIN_DB_URL = postgresql://$(DB_USER):$(DB_PASSWORD)@$(DB_HOST):$(DB_PORT)/postgres

# PostgreSQL connection string for application database
APP_DB_URL = postgresql://$(DB_USER):$(DB_PASSWORD)@$(DB_HOST):$(DB_PORT)/$(DB_NAME)

# Colors for output
GREEN  := \033[0;32m
YELLOW := \033[0;33m
RED    := \033[0;31m
NC     := \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)Storyline AI - Makefile Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make <target>"
	@echo ""
	@echo "$(YELLOW)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Environment:$(NC)"
	@echo "  ENV_FILE:    $(ENV_FILE)"
	@echo "  DB_HOST:     $(DB_HOST)"
	@echo "  DB_PORT:     $(DB_PORT)"
	@echo "  DB_NAME:     $(DB_NAME)"
	@echo "  DB_USER:     $(DB_USER)"

install: ## Install Python dependencies and CLI
	@echo "$(GREEN)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	pip install -e .
	@echo "$(GREEN)✓ Installation complete$(NC)"

install-dev: ## Install development dependencies
	@echo "$(GREEN)Installing development dependencies...$(NC)"
	pip install -r requirements.txt
	pip install -e ".[dev]"
	@echo "$(GREEN)✓ Development installation complete$(NC)"

test: ## Run tests with pytest (auto-creates test database)
	@echo "$(GREEN)Running tests...$(NC)"
	@echo "$(YELLOW)Note: Test database will be auto-created and cleaned up$(NC)"
	./venv/bin/pytest -v --cov=src --cov-report=term-missing

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(NC)"
	./venv/bin/pytest -v -m unit

test-integration: ## Run integration tests only
	@echo "$(GREEN)Running integration tests...$(NC)"
	./venv/bin/pytest -v -m integration

test-quick: ## Run tests without coverage (faster)
	@echo "$(GREEN)Running tests (no coverage)...$(NC)"
	./venv/bin/pytest -v

test-failed: ## Re-run only failed tests
	@echo "$(GREEN)Re-running failed tests...$(NC)"
	./venv/bin/pytest -v --lf

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	./venv/bin/ptw -- -v

clean: ## Clean up temporary files and caches
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -f {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

create-db: ## Create the database
	@echo "$(GREEN)Creating database: $(DB_NAME)...$(NC)"
	@psql "$(ADMIN_DB_URL)" -c "CREATE DATABASE $(DB_NAME);" 2>/dev/null || \
		(echo "$(YELLOW)⚠ Database $(DB_NAME) may already exist$(NC)" && exit 0)
	@echo "$(GREEN)✓ Database created$(NC)"

drop-db: ## Drop the database (WARNING: destructive)
	@echo "$(RED)WARNING: This will permanently delete database: $(DB_NAME)$(NC)"
	@echo "Press Ctrl+C to cancel, or Enter to continue..." && read confirm
	@echo "$(RED)Dropping database: $(DB_NAME)...$(NC)"
	@psql "$(ADMIN_DB_URL)" -c "DROP DATABASE IF EXISTS $(DB_NAME);"
	@echo "$(GREEN)✓ Database dropped$(NC)"

init-db: ## Initialize database schema (requires database to exist)
	@echo "$(GREEN)Initializing database schema...$(NC)"
	@psql "$(APP_DB_URL)" -f scripts/setup_database.sql
	@echo "$(GREEN)✓ Schema initialized$(NC)"

setup-db: create-db init-db ## Create database and initialize schema
	@echo "$(GREEN)✓ Database setup complete$(NC)"

reset-db: drop-db setup-db ## Drop and recreate database (WARNING: destructive)
	@echo "$(GREEN)✓ Database reset complete$(NC)"

check-db: ## Check if database exists and is accessible
	@echo "$(GREEN)Checking database connection...$(NC)"
	@psql "$(APP_DB_URL)" -c "SELECT version();" >/dev/null 2>&1 && \
		echo "$(GREEN)✓ Database is accessible$(NC)" || \
		echo "$(RED)✗ Cannot connect to database$(NC)"

check-health: ## Run application health checks
	@echo "$(GREEN)Running health checks...$(NC)"
	storyline-cli check-health

index-media: ## Index media files from MEDIA_DIR
	@echo "$(GREEN)Indexing media files...$(NC)"
	@if [ -z "$(DIR)" ]; then \
		echo "$(YELLOW)Usage: make index-media DIR=path/to/media$(NC)"; \
		exit 1; \
	fi
	storyline-cli index-media $(DIR)

create-schedule: ## Create posting schedule (default: 7 days)
	@echo "$(GREEN)Creating posting schedule...$(NC)"
	storyline-cli create-schedule --days $(or $(DAYS),7)

list-queue: ## List pending queue items
	storyline-cli list-queue

list-media: ## List indexed media items
	storyline-cli list-media --limit $(or $(LIMIT),50)

list-users: ## List all users
	storyline-cli list-users

run: ## Run the main application
	@echo "$(GREEN)Starting Storyline AI...$(NC)"
	python -m src.main

dev: ## Run in development mode with environment validation
	@echo "$(GREEN)Starting in development mode...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ .env file not found. Copy .env.example to .env and configure it.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Environment file found$(NC)"
	@make check-health
	python -m src.main

logs: ## View application logs (tail -f)
	@echo "$(GREEN)Tailing logs...$(NC)"
	tail -f logs/storyline.log

db-shell: ## Open PostgreSQL shell for application database
	@echo "$(GREEN)Opening database shell...$(NC)"
	psql "$(APP_DB_URL)"

db-backup: ## Backup database to file
	@echo "$(GREEN)Backing up database...$(NC)"
	@mkdir -p backups
	@BACKUP_FILE="backups/$(DB_NAME)_$$(date +%Y%m%d_%H%M%S).sql"; \
	pg_dump "$(APP_DB_URL)" > $$BACKUP_FILE && \
	echo "$(GREEN)✓ Backup saved to: $$BACKUP_FILE$(NC)"

db-restore: ## Restore database from backup (Usage: make db-restore FILE=path/to/backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)✗ Usage: make db-restore FILE=path/to/backup.sql$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)WARNING: This will restore database from: $(FILE)$(NC)"
	@echo "Press Ctrl+C to cancel, or Enter to continue..." && read confirm
	@echo "$(GREEN)Restoring database...$(NC)"
	@psql "$(APP_DB_URL)" < $(FILE)
	@echo "$(GREEN)✓ Database restored$(NC)"

env-example: ## Copy .env.example to .env
	@if [ -f .env ]; then \
		echo "$(YELLOW)⚠ .env file already exists. Skipping...$(NC)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(NC)"; \
		echo "$(YELLOW)→ Please edit .env and configure your settings$(NC)"; \
	fi

quickstart: env-example install setup-db ## Quick start: setup everything for first-time use
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ Quickstart Complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit .env and configure your settings"
	@echo "  2. Run: make index-media DIR=media/stories"
	@echo "  3. Run: make create-schedule"
	@echo "  4. Run: make run"
	@echo ""

validate-env: ## Validate environment configuration
	@echo "$(GREEN)Validating environment configuration...$(NC)"
	@python -c "from src.config.settings import get_settings; get_settings()" && \
		echo "$(GREEN)✓ Configuration is valid$(NC)" || \
		echo "$(RED)✗ Configuration validation failed$(NC)"

.DEFAULT_GOAL := help
