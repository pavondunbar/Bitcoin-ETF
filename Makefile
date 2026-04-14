# =========================
# Bitcoin ETF Simulator
# =========================

.PHONY: help build up down logs trigger rebuild clean ps

help:
	@echo "Available commands:"
	@echo "  make build     - Build all containers"
	@echo "  make up        - Start system (detached)"
	@echo "  make down      - Stop system"
	@echo "  make logs      - Follow logs"
	@echo "  make trigger   - Simulate ETF inflow"
	@echo "  make rebuild   - Full rebuild (no cache)"
	@echo "  make ps        - Show running containers"
	@echo "  make clean     - Remove containers + volumes"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

trigger:
	curl -X POST http://localhost:8000/create \
	-H "Content-Type: application/json" \
	-d '{"cash":1000000}'

rebuild:
	docker-compose build --no-cache

ps:
	docker-compose ps

clean:
	docker-compose down -v --remove-orphans
