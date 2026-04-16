.PHONY: up down backend-test iris-install iris-up iris-down iris-logs iris-admin-password require-docker

ROOT_DIR := $(shell pwd)
IRIS_WEB_DIR ?= $(ROOT_DIR)/.vendor/iris-web
IRIS_WEB_REF ?= v2.4.27

up:
	bash scripts/dev-up.sh

down:
	bash scripts/dev-down.sh

backend-test:
	cd backend && python -m pytest -q

iris-install:
	bash scripts/iris/install_iris_web.sh "$(IRIS_WEB_DIR)" "$(IRIS_WEB_REF)"

require-docker:
	@command -v docker >/dev/null 2>&1 || (echo "docker CLI not found. Install Docker Desktop and retry." && exit 1)

iris-up: require-docker iris-install
	cd "$(IRIS_WEB_DIR)" && docker compose up -d

iris-down: require-docker
	cd "$(IRIS_WEB_DIR)" && docker compose down

iris-logs: require-docker
	cd "$(IRIS_WEB_DIR)" && docker compose logs -f app

iris-admin-password: require-docker
	cd "$(IRIS_WEB_DIR)" && docker compose logs app | grep "create_safe_admin" | tail -1
