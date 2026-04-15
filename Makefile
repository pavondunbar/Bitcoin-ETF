############################################################
# CCP / ETF Clearing Infrastructure - Production Makefile
# Institutional-grade orchestration layer
############################################################

SHELL := /bin/bash

COMPOSE := docker compose
PROJECT := ccp-etf

############################################################
# HELP
############################################################

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "CCP ETF Infrastructure - Available Commands"
	@echo "-------------------------------------------"
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS=":.*##"} {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""

############################################################
# BOOTSTRAP (ORDERED STARTUP)
############################################################

.PHONY: bootstrap
bootstrap: migrate kafka-init up ## Full system bootstrap (safe start)
	@echo "[BOOTSTRAP] system initialized"

############################################################
# LIFECYCLE
############################################################

.PHONY: up
up: ## Start full stack (Kafka, Postgres, MPC, services)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop full stack
	$(COMPOSE) down

.PHONY: restart
restart: down up ## Restart full stack

.PHONY: ps
ps: ## Show running containers
	$(COMPOSE) ps

.PHONY: build
build: ## Build all images
	$(COMPOSE) build --no-cache

.PHONY: clean
clean: ## Destroy stack + volumes (DANGEROUS)
	$(COMPOSE) down -v --remove-orphans

############################################################
# DEMO / LIFECYCLE
############################################################

.PHONY: demo
demo: migrate kafka-init ## Run full ETF/CCP lifecycle demo
	python3 run_demo.py

############################################################
# HEALTH & OBSERVABILITY
############################################################

.PHONY: health
health: ## Check system health across all services
	python3 scripts/health_check.py

.PHONY: logs
logs: ## Tail all logs
	$(COMPOSE) logs -f --tail=200

.PHONY: logs-api
logs-api:
	$(COMPOSE) logs -f api-gateway

.PHONY: logs-settlement
logs-settlement:
	$(COMPOSE) logs -f settlement-engine

.PHONY: logs-margin
logs-margin:
	$(COMPOSE) logs -f margin-engine

############################################################
# DATABASE (POSTGRES - LEDGER SYSTEM)
############################################################

.PHONY: shell-pg
shell-pg: ## Open PostgreSQL shell
	$(COMPOSE) exec postgres psql -U postgres -d ccp

.PHONY: db-ledger
db-ledger: ## Inspect journal entries (double-entry ledger)
	$(COMPOSE) exec postgres psql -U postgres -d ccp -c \
	"SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT 50;"

.PHONY: db-balances
db-balances: ## Show derived account balances (NO MUTATION SOURCE OF TRUTH)
	$(COMPOSE) exec postgres psql -U postgres -d ccp -c \
	"SELECT * FROM account_balances WHERE balance != 0;"

.PHONY: db-rtgs
db-rtgs: ## Settlement instructions (CCP clearing layer)
	$(COMPOSE) exec postgres psql -U postgres -d ccp -c \
	"SELECT * FROM settlement_instructions ORDER BY created_at DESC;"

.PHONY: db-fx
db-fx: ## FX exposures (if multi-currency enabled)
	$(COMPOSE) exec postgres psql -U postgres -d ccp -c \
	"SELECT * FROM fx_exposures;"

############################################################
# MIGRATIONS (FIXED IMPORT ISSUE)
############################################################

.PHONY: migrate
migrate: ## Run database migrations (PYTHONPATH-safe)
	PYTHONPATH=. python3 -m scripts.migrate

############################################################
# KAFKA (EVENT-DRIVEN CORE)
############################################################

.PHONY: topics
topics: ## List Kafka topics
	$(COMPOSE) exec kafka kafka-topics --bootstrap-server kafka:9092 --list

.PHONY: kafka-init
kafka-init: ## Create base Kafka topics (safe bootstrap)
	$(COMPOSE) exec kafka kafka-topics \
	--bootstrap-server kafka:9092 \
	--create \
	--if-not-exists \
	--topic trades \
	--partitions 1 \
	--replication-factor 1 || true

	$(COMPOSE) exec kafka kafka-topics \
	--bootstrap-server kafka:9092 \
	--create \
	--if-not-exists \
	--topic event_log \
	--partitions 1 \
	--replication-factor 1 || true

.PHONY: kafka-tail
kafka-tail: ## Tail Kafka topic (use TOPIC=name)
	@echo "Usage: make kafka-tail TOPIC=your.topic"
	@test -n "$(TOPIC)" || (echo "ERROR: TOPIC is required" && exit 1)
	$(COMPOSE) exec kafka kafka-console-consumer \
	--bootstrap-server kafka:9092 \
	--topic $(TOPIC) \
	--from-beginning

############################################################
# TESTING
############################################################

.PHONY: test
test: ## Run full test suite
	pytest tests/ -v

.PHONY: test-unit
test-unit: ## Run unit tests only
	pytest tests/unit -v

.PHONY: test-e2e
test-e2e: ## Run end-to-end lifecycle tests
	pytest tests/integration -v

############################################################
# INTEGRITY (CCP REQUIREMENT)
############################################################

.PHONY: integrity
integrity: ## Ledger replay + invariants + reconciliation
	python3 scripts/integrity_check.py

############################################################
# SEEDING
############################################################

.PHONY: seed-accounts
seed-accounts: ## Seed members, accounts, instruments
	python3 scripts/seed_accounts.py

############################################################
# OBSERVABILITY
############################################################

.PHONY: monitoring-up
monitoring-up: ## Start Prometheus + Grafana
	$(COMPOSE) -f docker-compose.monitoring.yml up -d

.PHONY: monitoring-down
monitoring-down: ## Stop observability stack
	$(COMPOSE) -f docker-compose.monitoring.yml down

############################################################
# DOCS
############################################################

.PHONY: open-docs
open-docs: ## Open API documentation
	open http://localhost:8000/docs || true

############################################################
# DEBUGGING
############################################################

.PHONY: shell-kafka
shell-kafka: ## Open Kafka container shell
	$(COMPOSE) exec kafka bash

.PHONY: shell-margin
shell-margin:
	$(COMPOSE) exec margin-engine bash

.PHONY: shell-settlement
shell-settlement:
	$(COMPOSE) exec settlement-engine bash

############################################################
# SAFETY
############################################################

.PHONY: guard-prod
guard-prod:
	@echo "WARNING: Production mode not enabled in this repo"
	@exit 1

############################################################
# FULL RESET (DANGEROUS)
############################################################

.PHONY: nuke
nuke: clean ## Hard reset (all volumes + state destroyed)
	@echo "ALL STATE DESTROYED"

############################################################
# DEFAULT
############################################################

.DEFAULT_GOAL := help
