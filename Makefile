.PHONY: dev test lint docker-build web-install web-build web-dev check

dev:
	flask --app main:application run --debug --port 8080

test:
	pytest tests/ -v

lint:
	ruff check .
	ruff format --check .

docker-build:
	docker build -t apimodelregression:dev .

web-install:
	cd web && npm ci

web-build:
	cd web && npm run build

web-dev:
	cd web && npm run dev

# Full local gate: lint, backend tests, frontend typecheck+build.
check: lint test web-build
