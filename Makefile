.PHONY: up down api-test web-test seed demo generate-api

up:
	docker compose up --build

down:
	docker compose down

api-test:
	docker compose run --rm api pytest

web-test:
	docker compose run --rm web npm test

seed:
	docker compose exec api python -m atlas.seed

demo:
	python3 tools/test-runner/simulate.py thermal-failure

generate-api:
	cd apps/web && npm run generate:api

