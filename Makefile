.PHONY: help up down test demo logs train clean

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

up: ## Start all Sentinel services
	docker compose up -d --build
	@echo "Waiting 30s for services to initialize..."
	@sleep 30
	@docker compose ps

down: ## Stop all services
	docker compose down

test: ## Run 30-point validation suite
	bash scripts/validate_sentinel.sh

demo: ## Run the live demo script
	bash scripts/demo.sh

logs: ## Tail all docker compose logs
	docker compose logs -f

train: ## Train ML models inside container
	docker compose run --rm ml-service bash -c "python3 ml/train_xgboost.py && python3 ml/train_isolation_forest.py"

clean: ## Destroy all containers, volumes, and data
	docker compose down -v
