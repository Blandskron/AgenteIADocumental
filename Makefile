.PHONY: install run-chat run-embedding run-search run-access test lint process-pending docker-build docker-up docker-up-infra docker-up-documents

install:
	pip install -r backend/RagDocumentEmbeddingServices/requirements.txt
	pip install -r backend/RagDocumentChatServices/requirements.txt
	pip install -r backend/DocumentSearchServices/requirements.txt
	pip install -r backend/DocumentAccessServices/requirements.txt

run-chat:
	cd backend/RagDocumentChatServices && uvicorn app.main:app --reload --host 0.0.0.0 --port 8002

run-embedding:
	cd backend/RagDocumentEmbeddingServices && uvicorn app.main:app --reload --host 0.0.0.0 --port 8003

run-search:
	cd backend/DocumentSearchServices && uvicorn app.main:app --reload --host 0.0.0.0 --port 8004

run-access:
	cd backend/DocumentAccessServices && uvicorn app.main:app --reload --host 0.0.0.0 --port 8005

test:
	pytest

lint:
	ruff check backend/RagDocumentChatServices/app backend/RagDocumentEmbeddingServices/app backend/DocumentSearchServices/app backend/DocumentAccessServices/app scripts

process-pending:
	python scripts/process_pending_documents.py

docker-build:
	docker build -f backend/RagDocumentChatServices/Dockerfile -t rag-document-chat-service backend/RagDocumentChatServices
	docker build -f backend/RagDocumentEmbeddingServices/Dockerfile -t rag-document-embedding-service backend/RagDocumentEmbeddingServices
	docker build -f backend/DocumentSearchServices/Dockerfile -t document-search-service backend/DocumentSearchServices
	docker build -f backend/DocumentAccessServices/Dockerfile -t document-access-service backend/DocumentAccessServices

docker-up:
	docker compose -f docker/docker-compose.yml up --build

docker-up-infra:
	cd docker && docker compose -f compose/infra.yml -f compose/auth.yml up --build

docker-up-documents:
	cd docker && docker compose -f compose/infra.yml -f compose/auth.yml -f compose/documents.yml up --build
