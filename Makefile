ENGINE ?= podman
REGISTRY ?= quay.io/ops-buddy
TAG ?= latest

.PHONY: up down restart debug debug-no-cache build push prod-up prod-down

default: up

# Development targets (build locally)
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

# Production targets (use pre-built images)
prod-up:
	$(ENGINE) compose -f compose.prod.yml --env-file config.env up -d

prod-down:
	$(ENGINE) compose -f compose.prod.yml --env-file config.env down

# Build all images for production
build:
	$(ENGINE) build -t $(REGISTRY)/rhoai-ops-graph:$(TAG) -f containers/Containerfile.agents .
	$(ENGINE) build -t $(REGISTRY)/chat-ui:$(TAG) -f containers/Containerfile.chat-ui .
	$(ENGINE) build -t $(REGISTRY)/rhoai-jenkins-mcp:$(TAG) -f ../rhoai-jenkins-mcp/Containerfile ../rhoai-jenkins-mcp
	$(ENGINE) build -t $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG) -f ../rhoai-cluster-monitor-mcp/Containerfile ../rhoai-cluster-monitor-mcp

# Push all images to registry
push: build
	$(ENGINE) push $(REGISTRY)/rhoai-ops-graph:$(TAG)
	$(ENGINE) push $(REGISTRY)/chat-ui:$(TAG)
	$(ENGINE) push $(REGISTRY)/rhoai-jenkins-mcp:$(TAG)
	$(ENGINE) push $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG)

# Build and push specific images
push-ops-graph:
	$(ENGINE) build -t $(REGISTRY)/rhoai-ops-graph:$(TAG) -f containers/Containerfile.agents .
	$(ENGINE) push $(REGISTRY)/rhoai-ops-graph:$(TAG)

push-chat-ui:
	$(ENGINE) build -t $(REGISTRY)/chat-ui:$(TAG) \
		--build-arg NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) \
		--build-arg NEXT_PUBLIC_ASSISTANT_ID=agent \
		-f containers/Containerfile.chat-ui .
	$(ENGINE) push $(REGISTRY)/chat-ui:$(TAG)

push-jenkins-mcp:
	$(ENGINE) build -t $(REGISTRY)/rhoai-jenkins-mcp:$(TAG) -f ../rhoai-jenkins-mcp/Containerfile ../rhoai-jenkins-mcp
	$(ENGINE) push $(REGISTRY)/rhoai-jenkins-mcp:$(TAG)

push-cluster-monitor:
	$(ENGINE) build -t $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG) -f ../rhoai-cluster-monitor-mcp/Containerfile ../rhoai-cluster-monitor-mcp
	$(ENGINE) push $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG)
