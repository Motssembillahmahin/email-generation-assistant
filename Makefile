.DEFAULT_GOAL := help
.PHONY: help setup generate eval test lint format clean

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## Install dependencies into a uv-managed virtualenv
	uv sync

generate:  ## Generate one demo email (use ARGS="--intent ... --tone ...")
	uv run python -m email_assistant.cli $(ARGS)

eval:  ## Run the full evaluation (10 scenarios x 2 models) -> results/
	uv run python -m email_assistant.evaluate

test:  ## Run the pytest suite
	uv run pytest

lint:  ## Lint with ruff
	uv run ruff check .

format:  ## Auto-format with ruff
	uv run ruff format .

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
