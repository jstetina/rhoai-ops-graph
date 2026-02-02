ENGINE ?= podman
REGISTRY ?= quay.io/ops-buddy
TAG ?= latest

# Configuration files
DEV_ENV ?= config/dev.env
PROD_ENV ?= config/prod.env

# Chat UI build-time variables (override via env or command line)
# Example: make push-chat-ui NEXT_PUBLIC_API_URL=https://ops-buddy.apps.cluster.example.com/api
NEXT_PUBLIC_API_URL ?= /api
NEXT_PUBLIC_ASSISTANT_ID ?= agent

.PHONY: dev-up dev-down dev-restart dev-rebuild dev-debug dev-debug-no-cache \
	prod-up prod-down build push \
	push-ops-graph push-chat-ui push-jenkins-mcp push-cluster-monitor \
	ocp-install ocp-upgrade ocp-uninstall

default: dev-up

# =============================================================================
# Development targets (build locally, direct browser connection to LangGraph)
# =============================================================================
dev-up:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) up -d --build

dev-down:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) down

dev-restart:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) restart

dev-debug:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) up --build

dev-debug-no-cache:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) up --build --no-cache

dev-rebuild:
	$(ENGINE) compose -f compose.yml --env-file $(DEV_ENV) up -d --build --no-cache

# =============================================================================
# Production targets (use pre-built images with API passthrough)
# =============================================================================
prod-up:
	$(ENGINE) compose -f compose.prod.yml --env-file $(PROD_ENV) up -d

prod-down:
	$(ENGINE) compose -f compose.prod.yml --env-file $(PROD_ENV) down

prod-restart:
	$(ENGINE) compose -f compose.prod.yml --env-file $(PROD_ENV) restart

# =============================================================================
# Build and push images
# =============================================================================
# Chat UI build args:
#   NEXT_PUBLIC_API_URL - Browser's API endpoint (default: /api for portability)
#   NEXT_PUBLIC_ASSISTANT_ID - Assistant ID (default: agent)
#
# Override for specific deployments:
#   make push-chat-ui NEXT_PUBLIC_API_URL=https://ops-buddy.apps.cluster.example.com/api

# Build all images for production
build:
	$(ENGINE) build -t $(REGISTRY)/rhoai-ops-graph:$(TAG) -f containers/Containerfile.agents .
	$(ENGINE) build -t $(REGISTRY)/chat-ui:$(TAG) \
		--build-arg NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) \
		--build-arg NEXT_PUBLIC_ASSISTANT_ID=$(NEXT_PUBLIC_ASSISTANT_ID) \
		-f containers/Containerfile.chat-ui .
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
		--build-arg NEXT_PUBLIC_ASSISTANT_ID=$(NEXT_PUBLIC_ASSISTANT_ID) \
		-f containers/Containerfile.chat-ui .
	$(ENGINE) push $(REGISTRY)/chat-ui:$(TAG)

push-jenkins-mcp:
	$(ENGINE) build -t $(REGISTRY)/rhoai-jenkins-mcp:$(TAG) -f ../rhoai-jenkins-mcp/Containerfile ../rhoai-jenkins-mcp
	$(ENGINE) push $(REGISTRY)/rhoai-jenkins-mcp:$(TAG)

push-cluster-monitor:
	$(ENGINE) build -t $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG) -f ../rhoai-cluster-monitor-mcp/Containerfile ../rhoai-cluster-monitor-mcp
	$(ENGINE) push $(REGISTRY)/rhoai-cluster-monitor-mcp:$(TAG)

# =============================================================================
# OpenShift deployment (Helm)
# =============================================================================
HELM_RELEASE ?= ops-buddy
HELM_NAMESPACE ?= rhoai-ops
HELM_VALUES ?= k8s/ops-buddy/values.yaml

# Extract credential paths from values.yaml
HIVE_KUBECONFIG := $(shell yq '.clusterMonitor.hive.kubeconfigPath // ""' $(HELM_VALUES))
AWS_CREDENTIALS := $(shell yq '.clusterMonitor.aws.credentialsPath // ""' $(HELM_VALUES))

# Build --set-file args if credential paths exist and files are readable
HELM_SET_FILES :=
ifneq ($(HIVE_KUBECONFIG),)
ifneq ($(wildcard $(HIVE_KUBECONFIG)),)
HELM_SET_FILES += --set-file clusterMonitor.hive.kubeconfigContent=$(HIVE_KUBECONFIG)
endif
endif
ifneq ($(AWS_CREDENTIALS),)
ifneq ($(wildcard $(AWS_CREDENTIALS)),)
HELM_SET_FILES += --set-file clusterMonitor.aws.credentialsContent=$(AWS_CREDENTIALS)
endif
endif

ocp-install:
	helm install $(HELM_RELEASE) k8s/ops-buddy \
		--namespace $(HELM_NAMESPACE) \
		-f $(HELM_VALUES) \
		$(HELM_SET_FILES)

ocp-upgrade:
	helm upgrade $(HELM_RELEASE) k8s/ops-buddy \
		--namespace $(HELM_NAMESPACE) \
		-f $(HELM_VALUES) \
		$(HELM_SET_FILES)

ocp-uninstall:
	helm uninstall $(HELM_RELEASE) --namespace $(HELM_NAMESPACE)
