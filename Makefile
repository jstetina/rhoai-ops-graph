ENGINE ?= podman

.PHONY: up down

default: up

up:
	$(ENGINE) compose -f compose.yml --env-file config.env up -d --build

down:
	$(ENGINE) compose -f compose.yml --env-file config.env down

restart:
	$(ENGINE) compose -f compose.yml --env-file config.env restart


debug-no-cache:
	$(ENGINE) compose -f compose.yml --env-file config.env up --build --no-cache

debug:
	$(ENGINE) compose -f compose.yml --env-file config.env up --build
