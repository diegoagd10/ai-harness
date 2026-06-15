# Python migration slice (uv-managed). The Go targets remain the reference and
# fallback for install/uninstall and any command outside the migrated SDD scope;
# this Makefile drives only the Python foundation (sdd-status).

.DEFAULT_GOAL := help

.PHONY: help test coverage lint fmt fmt-check go-build go-test

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## Run the Python test suite
	uv run pytest

coverage: ## Run tests under coverage and print the report
	uv run coverage run -m pytest && uv run coverage report

lint: ## Lint Python sources with ruff
	uv run ruff check

fmt: ## Format Python sources in place with ruff
	uv run ruff format

fmt-check: ## Verify Python formatting without writing changes
	uv run ruff format --check

go-build: ## Compile the reference Go binary (migration fallback)
	go build -o ai-harness ./cmd/ai-harness

go-test: ## Run the reference Go test suite (migration fallback)
	go test ./...
