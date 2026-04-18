.PHONY: help up down test demo logs train train-multisource datasets clean

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

train: ## Prepare dataset + train ML models inside container
	docker compose run --rm --user root ml-service bash -lc "ln -sfn /app/models /app/model_weights && python3 scripts/prepare_dataset.py && python3 ml/train_xgboost.py && python3 ml/train_isolation_forest.py"

train-multisource: ## Build multi-source dataset + train ML models locally
	USE_MULTISOURCE_DATA=1 bash scripts/train.sh

datasets: ## Download open public datasets for local multi-source training
	bash scripts/fetch_public_datasets.sh core

clean: ## Destroy all containers, volumes, and data
	docker compose down -v
