# Blandskron Documental — Makefile operativo (11 servicios backend + frontend + verificación)
# Ejecutar siempre desde la raíz del repositorio.
# Sobrescribe variables si necesitas otro archivo de entorno o proyecto:
#   make ENV_FILE=.env.local up

SHELL := /bin/bash
ENV_FILE ?= .env
COMPOSE_FILE ?= docker/docker-compose.yml
COMPOSE := docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
VERIFICATION_PROJECT ?= bd-final-check
PYTHON ?= python3

BACKEND_SERVICES := \
	AuthServices \
	RagDocumentChatServices \
	RagDocumentEmbeddingServices \
	DocumentSearchServices \
	DocumentAccessServices \
	DocumentLibraryServices \
	DocumentTransferServices \
	ConversationServices \
	ProfileServices \
	DocumentExportServices \
	GoogleDriveImportServices

FASTAPI_SERVICES := \
	RagDocumentChatServices \
	RagDocumentEmbeddingServices \
	DocumentSearchServices \
	DocumentAccessServices \
	DocumentLibraryServices \
	DocumentTransferServices \
	ConversationServices \
	ProfileServices \
	DocumentExportServices \
	GoogleDriveImportServices

COMPOSE_TEST_SERVICES := \
	rag-chat-tests \
	embedding-tests \
	search-tests \
	access-tests \
	library-tests \
	transfer-tests \
	conversation-tests \
	profile-tests \
	export-tests \
	drive-tests

.PHONY: help \
	compose-config up down restart ps logs psql \
	docker-build docker-up docker-up-infra docker-up-documents \
	run-auth run-chat run-embedding run-search run-access run-library \
	run-transfer run-conversation run-profile run-export run-drive run-frontend \
	install lint check-docs eval-baseline eval-studio \
	test test-auth test-services test-frontend build-frontend \
	process-pending reindex \
	verify-prepare verify verify-relations verify-postgres-upgrade verify-images verify-graphs verify-down

help: ## Muestra los comandos disponibles
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker Compose (flujo principal soportado)
# ---------------------------------------------------------------------------

compose-config: ## Valida el contrato Docker Compose con ENV_FILE
	$(COMPOSE) config --quiet

up: ## Construye y levanta el stack completo esperando salud de todos los servicios
	$(COMPOSE) up -d --build --wait

down: ## Detiene y retira contenedores conservando volúmenes de datos
	$(COMPOSE) down --remove-orphans

restart: ## Reinicia los servicios activos del stack
	$(COMPOSE) restart

ps: ## Lista el estado de todos los contenedores y jobs del stack
	$(COMPOSE) ps -a

logs: ## Muestra los últimos logs del stack (usa SERVICE=auth-service para filtrar)
	$(COMPOSE) logs --tail 100 $(SERVICE)

psql: ## Abre una sesión psql local contra documents_db
	$(COMPOSE) exec postgres psql -U postgres -d documents_db

docker-build: ## Construye todas las imágenes definidas en docker/docker-compose.yml
	$(COMPOSE) build

docker-up: up ## Alias de 'up' para compatibilidad

docker-up-infra: ## Levanta únicamente PostgreSQL, esquema y Auth
	$(COMPOSE) up -d --build --wait auth-service

docker-up-documents: ## Levanta infraestructura, Auth y servicios documentales principales
	$(COMPOSE) up -d --build --wait \
		auth-service \
		rag-document-embedding-service \
		rag-document-chat-service \
		document-search-service \
		document-access-service \
		document-library-service \
		document-transfer-service

# ---------------------------------------------------------------------------
# Desarrollo local por servicio (sin Docker)
# ---------------------------------------------------------------------------

install: ## Instala dependencias Python de los 11 servicios en el entorno activo
	@set -e; for svc in $(BACKEND_SERVICES); do \
		echo "==> Instalando requisitos de $$svc"; \
		$(PYTHON) -m pip install -r "backend/$$svc/requirements.txt"; \
	done

run-auth: ## Ejecuta AuthServices (Django, puerto 8001)
	cd backend/AuthServices && $(PYTHON) manage.py runserver 127.0.0.1:8001

run-chat: ## Ejecuta RagDocumentChatServices (puerto 8002)
	cd backend/RagDocumentChatServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8002

run-embedding: ## Ejecuta RagDocumentEmbeddingServices (puerto 8003)
	cd backend/RagDocumentEmbeddingServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8003

run-search: ## Ejecuta DocumentSearchServices (puerto 8004)
	cd backend/DocumentSearchServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8004

run-access: ## Ejecuta DocumentAccessServices (puerto 8005)
	cd backend/DocumentAccessServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8005

run-library: ## Ejecuta DocumentLibraryServices (puerto 8006)
	cd backend/DocumentLibraryServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8006

run-transfer: ## Ejecuta DocumentTransferServices (puerto 8007)
	cd backend/DocumentTransferServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8007

run-conversation: ## Ejecuta ConversationServices (puerto 8008)
	cd backend/ConversationServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8008

run-profile: ## Ejecuta ProfileServices (puerto 8015)
	cd backend/ProfileServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8015

run-export: ## Ejecuta DocumentExportServices (puerto 8016)
	cd backend/DocumentExportServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8016

run-drive: ## Ejecuta GoogleDriveImportServices (puerto 8017)
	cd backend/GoogleDriveImportServices && uvicorn app.main:app --reload --host 127.0.0.1 --port 8017

run-frontend: ## Ejecuta el frontend React/Vite en desarrollo
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Calidad, enlaces y pruebas
# ---------------------------------------------------------------------------

check-docs: ## Valida enlaces Markdown relativos en raíz y docs/
	$(PYTHON) scripts/ci/check_docs_links.py

eval-baseline: ## Ejecuta el harness sintético S1-S5 y genera .release-reports/EVAL_BASELINE.json
	$(PYTHON) scripts/eval/run_eval_baseline.py

eval-studio: ## Ejecuta el gate de evaluación de Knowledge Studio y genera .release-reports/STUDIO_EVAL_GATE.json
	$(PYTHON) scripts/eval/run_studio_eval_gate.py

lint: ## Ejecuta ruff sobre todos los servicios backend y scripts Python
	ruff check \
		backend/AuthServices \
		$(foreach svc,$(FASTAPI_SERVICES),backend/$(svc)/app) \
		scripts

test-auth: ## Ejecuta tests Django de AuthServices en entorno local
	cd backend/AuthServices && $(PYTHON) manage.py test

test-services: ## Ejecuta las suites de pruebas de los 10 servicios FastAPI en Docker Compose
	@set -e; for svc in $(COMPOSE_TEST_SERVICES); do \
		echo "==> Ejecutando $$svc"; \
		$(COMPOSE) run --rm "$$svc"; \
	done

test-frontend: ## Ejecuta tests unitarios del frontend (Vitest)
	cd frontend && npm test

build-frontend: ## Compila el frontend en modo producción
	cd frontend && npm run build

test: check-docs test-frontend ## Ejecuta comprobaciones locales rápidas (docs + frontend)

# ---------------------------------------------------------------------------
# Procesamiento documental directo
# ---------------------------------------------------------------------------

process-pending: ## Procesa documentos pendientes (usa LIMIT=10)
	$(PYTHON) scripts/process_pending_documents.py --limit $(or $(LIMIT),10)

reindex: ## Reindexa documentos existentes (usa LIMIT=100)
	$(PYTHON) scripts/reindex_documents.py --all --limit $(or $(LIMIT),100)

# ---------------------------------------------------------------------------
# Verificación sintética de entrega (proyecto dedicado bd-final-check)
# ---------------------------------------------------------------------------

verify-prepare: ## Genera archivo de entorno sintético y muestra su ruta
	@node scripts/release/prepare_verification.mjs

verify: ## Ejecuta la verificación sintética completa sobre bd-final-check
	@set -e; \
	VERIFICATION_ENV_FILE="$$(node scripts/release/prepare_verification.mjs)"; \
	export VERIFICATION_ENV_FILE; \
	docker compose --env-file "$$VERIFICATION_ENV_FILE" -p $(VERIFICATION_PROJECT) \
		-f $(COMPOSE_FILE) -f docker/compose/verification.yml up -d --build --wait blandskron-frontend; \
	node scripts/release/verify.mjs

verify-relations: ## Ejecuta solo las suites SQL de roles y concurrencia sobre bd-final-check
	node scripts/release/verify.mjs --relations-only

verify-postgres-upgrade: ## Verifica migración/restauración lógica de PostgreSQL 16 + pgvector
	node scripts/release/verify_postgres_upgrade.mjs

verify-images: ## Ejecuta auditoría Trivy sobre las imágenes del proyecto bd-final-check
	node scripts/release/audit_images.mjs --project $(VERIFICATION_PROJECT)

verify-graphs: ## Valida los grafos de dependencias Python de las imágenes
	node scripts/release/verify_graphs.mjs

verify-down: ## Detiene los contenedores del proyecto sintético bd-final-check conservando volúmenes
	@if [ -z "$$VERIFICATION_ENV_FILE" ]; then \
		echo "Define VERIFICATION_ENV_FILE antes de ejecutar verify-down" >&2; \
		exit 1; \
	fi
	docker compose --env-file "$$VERIFICATION_ENV_FILE" -p $(VERIFICATION_PROJECT) \
		-f $(COMPOSE_FILE) -f docker/compose/verification.yml down --remove-orphans
