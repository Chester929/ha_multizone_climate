.PHONY: help build start stop restart logs clean test test-integration test-integration-verbose test-integration-clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all containers
	docker-compose build

build-logic: ## Build logic container only
	docker-compose build logic

start: ## Start all services
	docker-compose up -d

stop: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Show logs from all containers
	docker-compose logs -f

logs-logic: ## Show logs from logic container
	docker-compose logs -f logic

logs-redis: ## Show logs from Redis
	docker-compose logs -f redis

ps: ## Show running containers
	docker-compose ps

clean: ## Remove all containers and volumes
	docker-compose down -v

redis-cli: ## Connect to Redis CLI
	docker-compose exec redis redis-cli

test-logic: ## Run Go tests
	cd logic && go test ./...

lint-logic: ## Lint Go code
	cd logic && go vet ./...
	cd logic && gofmt -l .

dev-logic: ## Run logic container in development mode
	cd logic && go run cmd/server/main.go

init-env: ## Create .env file from example
	cp .env.example .env
	@echo ".env file created. Please edit it with your settings."

status: ## Check status of all services
	@echo "Checking services..."
	@curl -s http://localhost:8080/health | jq . || echo "Logic container not responding"

init-redis: ## Initialize Redis with example data
	./examples/init-redis.sh

reset-redis: ## Reset Redis data
	docker-compose exec redis redis-cli --scan --pattern "multizone:*" | xargs docker-compose exec -T redis redis-cli DEL
	@echo "Redis data cleared"

test-integration: ## Run integration tests
	cd tests/integration && docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
	cd tests/integration && docker-compose -f docker-compose.test.yml down

test-integration-verbose: ## Run integration tests with verbose output
	cd tests/integration && docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit --remove-orphans

test-integration-clean: ## Clean up integration test containers and volumes
	cd tests/integration && docker-compose -f docker-compose.test.yml down -v --remove-orphans
	@echo "Integration test containers and volumes removed"
