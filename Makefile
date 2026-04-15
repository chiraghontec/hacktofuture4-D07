PHONY: up down backend-test

up:
	bash scripts/dev-up.sh

down:
	bash scripts/dev-down.sh

backend-test:
	cd backend && python -m pytest -q
