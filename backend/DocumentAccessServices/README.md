# DocumentAccessServices

## Overview
DocumentAccessServices is a FastAPI-based microservice responsible for secure access, preview, download, content retrieval, and deletion of documents. It is designed for integration in a microservices architecture, supporting JWT authentication, PostgreSQL persistence, and local file storage resolution.

## Features
- Preview documents (inline viewing)
- Download documents (attachment)
- Retrieve document content (with chunking)
- Delete documents (with file removal)
- JWT-based authentication (access token required)
- Health check endpoints
- CORS support for frontend integration

## API Endpoints

### Health
- `GET /api/v1/health` — Service health check
- `GET /api/v1/health/db` — Database connectivity check

### Document Access (Authenticated)
- `GET /api/v1/documents/{document_id}/preview` — Preview a document (inline)
- `GET /api/v1/documents/{document_id}/download` — Download a document (attachment)
- `GET /api/v1/documents/{document_id}/content` — Get document content (optionally chunked)
- `DELETE /api/v1/documents/{document_id}` — Delete a document and its file

### Assignments and notifications (Authenticated)

- `GET /api/v1/documents/assigned-to-me`
- `GET /api/v1/documents/managed-by-me`
- `GET /api/v1/documents/notifications`
- `POST /api/v1/documents/notifications/{notification_id}/read`
- `POST /api/v1/documents/{document_id}/assignments`
- `POST /api/v1/documents/assignments/{assignment_id}/accept`
- `POST /api/v1/documents/assignments/{assignment_id}/reject`
- `POST /api/v1/documents/assignments/{assignment_id}/sign`
- `POST /api/v1/documents/assignments/{assignment_id}/cancel`
- `GET /api/v1/documents/assignments/{assignment_id}/events`

## Data Models

### Document
- `document_id`: str
- `filename`: str
- `storage_path`: str
- `mime_type`: str
- `status`: str
- `metadata`: dict
- `processing_error`: str | None
- `processed_at`: datetime | None
- `created_at`: datetime
- `updated_at`: datetime

### DocumentContentResponse
- `document_id`: str
- `filename`: str
- `content`: str
- `chunk_count`: int

### DocumentDeleteResponse
- `document_id`: str
- `filename`: str
- `deleted`: bool
- `file_deleted`: bool

## Authentication
All endpoints (except health checks) require a valid JWT access token in the `Authorization: Bearer <token>` header. The token is validated using the configured RSA public key and must have `token_type: access`.

## Architecture
- **FastAPI** for API layer
- **SQLAlchemy** for ORM/database access
- **PostgreSQL** as the database
- **Pydantic** for request/response validation
- **Docker** for containerization
- **CORS** enabled for frontend integration
- **Local file storage** with path resolution and security checks

## Project Structure
- `app/main.py`: FastAPI app setup, middleware, error handling
- `app/interfaces/api/router.py`: API router and endpoint registration
- `app/interfaces/api/v1/routes/`: Endpoint implementations
- `app/application/documents/use_cases/`: Business logic (use cases)
- `app/infrastructure/database/`: Models, repositories, DB connection
- `app/infrastructure/storage/`: Local file path resolver
- `app/config/`: Settings, security, logging
- `app/shared/`: Shared error classes

## Running the Service

Prepara el entorno según el [README principal](../../README.md) y ejecuta desde la raíz del repositorio.

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-access-service
curl http://localhost:8005/api/v1/health/db
```

Compose pasa explícitamente las variables del servicio. El chequeo de arranque verifica PostgreSQL, la clave pública JWT y la existencia del directorio de documentos. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Configura `ACCESS_CORS_ORIGINS` como arreglo JSON para otros orígenes.

Fuera de Compose, instala `requirements.txt` desde este directorio y configura `DATABASE_URL`, `AUTH_JWT_PUBLIC_KEY_PATH` y `DOCUMENT_STORAGE_BASE_PATH` en el entorno o en el `.env` del servicio. Ejecuta `python -m uvicorn app.main:app --port 8005`. En este modo, configura CORS con `CORS_ORIGINS`.

El [tablero de modernización](../../ROADMAP.md#documentaccessservices) registra los incrementos de permisos, archivos, borrado, asignaciones y operación que siguen a la configuración inicial.

## Example Requests

**Preview Document**
```
GET /api/v1/documents/{document_id}/preview
Authorization: Bearer <token>
```

**Download Document**
```
GET /api/v1/documents/{document_id}/download
Authorization: Bearer <token>
```

**Get Document Content**
```
GET /api/v1/documents/{document_id}/content?max_chunks=100
Authorization: Bearer <token>
```

**Delete Document**
```
DELETE /api/v1/documents/{document_id}
Authorization: Bearer <token>
```

## License
This project is licensed under the terms of the repository's LICENSE file.
