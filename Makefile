.PHONY: dev test lint docker-build

dev:
	flask --app main:application run --debug --port 8080

test:
	pytest tests/ -v

lint:
	ruff check .
	ruff format --check .

docker-build:
	docker build -t apimodelregression:dev .