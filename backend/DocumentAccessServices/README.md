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
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables or edit config as needed
3. Run with Uvicorn: `uvicorn app.main:app --reload`
4. Or use Docker: `docker build -t document-access-services . && docker run ...`

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
