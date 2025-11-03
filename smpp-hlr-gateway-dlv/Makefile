.PHONY: help build up down logs test lint clean healthcheck metrics

help:
	@echo "SMPP HLR Gateway - Available Commands:"
	@echo ""
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - Follow logs"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run code linting"
	@echo "  make clean        - Clean up containers and volumes"
	@echo "  make healthcheck  - Check service health"
	@echo "  make metrics      - Show Prometheus metrics"
	@echo "  make shell        - Open shell in gateway container"
	@echo "  make redis-cli    - Open Redis CLI"
	@echo ""

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@docker-compose ps

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f smpp-gateway

logs-all:
	docker-compose logs -f

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/test_hlr_client.py tests/test_handler_logic.py -v

test-integration:
	pytest tests/test_integration.py -v

lint:
	@echo "Running flake8..."
	flake8 src/ tests/ --max-line-length=100 --ignore=E501,W503
	@echo "Running mypy..."
	mypy src/ --ignore-missing-imports

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

healthcheck:
	@echo "Checking gateway health..."
	@docker exec smpp-gateway python main.py healthcheck && echo "✓ Gateway is healthy" || echo "✗ Gateway is unhealthy"
	@echo ""
	@echo "Checking Redis..."
	@docker exec smpp-redis redis-cli ping && echo "✓ Redis is healthy" || echo "✗ Redis is unhealthy"

metrics:
	@echo "Fetching Prometheus metrics..."
	@curl -s http://localhost:9091/metrics | grep -E "^(submit_|hlr_|delivrd_|active_)" | grep -v "^#"

shell:
	docker exec -it smpp-gateway /bin/bash

redis-cli:
	docker exec -it smpp-redis redis-cli

ps:
	docker-compose ps

stats:
	docker stats smpp-gateway smpp-redis --no-stream

install-dev:
	pip install -r requirements.txt
	pip install flake8 mypy black isort

format:
	black src/ tests/
	isort src/ tests/

# Test with example client
test-valid:
	python examples/test_client.py --msisdn 13476841841 --message "Test valid number"

test-invalid:
	python examples/test_client.py --msisdn 40722570240999 --message "Test invalid number"