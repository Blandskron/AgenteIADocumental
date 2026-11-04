# RagDocumentEmbeddingServices

## Overview
RagDocumentEmbeddingServices es un microservicio basado en FastAPI encargado de la ingestión, procesamiento, reindexación y consulta de estado de documentos para sistemas RAG (Retrieval-Augmented Generation). Permite subir documentos, procesarlos para generar embeddings, reindexar y consultar su estado, integrándose en una arquitectura de microservicios con autenticación JWT y persistencia en PostgreSQL.

## Features
- Subida de documentos con metadatos
- Procesamiento de documentos para generación de embeddings
- Reindexación de documentos
- Consulta de estado de procesamiento
- Endpoints autenticados vía JWT
- Health checks (servicio, base de datos, AI)
- CORS para integración frontend

## API Endpoints

### Health
- `GET /api/v1/health` — Verifica el estado del servicio
- `GET /api/v1/health/db` — Verifica la conectividad con la base de datos
- `GET /api/v1/health/ai` — Verifica la configuración del proveedor de AI

### Documentos (Authenticated)
- `POST /api/v1/documents/upload` — Sube un documento para procesamiento
  - **Form fields:**
    - `file`: archivo a subir
    - `metadata`: JSON string (opcional)
    - `process`: bool (opcional, default: true)
- `POST /api/v1/documents/{document_id}/process` — Procesa un documento existente
- `POST /api/v1/documents/{document_id}/reindex` — Reindexa un documento existente
- `GET /api/v1/documents/{document_id}/status` — Consulta el estado de procesamiento de un documento

## Data Models

### DocumentUploadResponse
- `document_id`: str
- `filename`: str
- `status`: str
- `mime_type`: str
- `storage_path`: str
- `metadata`: dict

### DocumentProcessResponse
- `document_id`: str
- `status`: str

### DocumentStatusResponse
- `document_id`: str
- `filename`: str
- `status`: str
- `mime_type`: str
- `storage_path`: str

## Authentication
Las rutas documentales requieren un JWT de acceso de AuthServices con firma RSA válida, `user_id` entero positivo y `exp` entero vigente. Cargar requiere el permiso activo `upload_documents`, administración del tenant activo o acceso de superadministrador. Google Drive reenvía el JWT del usuario y se rige por la misma regla.

El propietario, los administradores del tenant documental y quienes tengan `manage_documents` en ese tenant activo pueden procesar y reindexar. Los superadministradores tienen acceso global. Compartir un grupo da acceso al estado dentro del tenant, sin conceder permiso de reindexación. Las columnas de propiedad y tenant tienen prioridad sobre los metadatos históricos.

## Architecture
- **FastAPI** para la capa API
- **SQLAlchemy** para ORM/acceso a base de datos
- **PostgreSQL** como base de datos
- **Pydantic** para validación de requests/responses
- **Docker** para contenerización
- **CORS** habilitado para integración frontend
- **Procesamiento de embeddings** para búsqueda semántica

## Project Structure
- `app/main.py`: Setup de FastAPI, middleware, manejo de errores
- `app/interfaces/api/router.py`: Registro de rutas y endpoints
- `app/interfaces/api/v1/routes/`: Implementación de endpoints
- `app/application/documents/use_cases/`: Lógica de negocio de ingestión y procesamiento
- `app/domain/`: Entidades de dominio
- `app/infrastructure/database/`: Modelos, repositorios, conexión a BD
- `app/config/`: Configuración, seguridad, logging
- `app/shared/`: Clases de error compartidas

## Running the Service

Desde la raíz del repositorio, prepara el entorno según el [README principal](../../README.md) y ejecuta:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait rag-document-embedding-service
curl http://localhost:8003/api/v1/health/db
```

Compose pasa las variables de ingesta explícitamente y comprueba el acceso a PostgreSQL y a la clave JWT pública antes de declarar el servicio sano. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Para otro origen, configura `EMBEDDING_CORS_ORIGINS` como arreglo JSON.

`MAX_CHUNK_SIZE` y `CHUNK_OVERLAP` se expresan en caracteres. El tamaño debe ser positivo y el solapamiento debe estar entre cero y el tamaño del fragmento menos uno. Fuera de Compose, ejecuta desde este directorio con las dependencias instaladas y configura `DATABASE_URL`, `DOCUMENT_STORAGE_BASE_PATH` y `AUTH_JWT_PUBLIC_KEY_PATH` en el entorno o el `.env` del servicio. Inicia con `python -m uvicorn app.main:app --port 8003`.

Para comprobar los permisos con PostgreSQL local:

```sh
docker compose -f docker/docker-compose.yml cp backend/RagDocumentEmbeddingServices/tests/test_ingestion_access.py rag-document-embedding-service:/app/test_ingestion_access.py
docker compose -f docker/docker-compose.yml exec -T rag-document-embedding-service python -m pytest -q test_ingestion_access.py
```

## Example Requests

**Subir documento**
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data
file: contrato.pdf
metadata: {"project": "Alpha"}
process: true
Authorization: Bearer <token>
```

**Procesar documento existente**
```
POST /api/v1/documents/{document_id}/process
Authorization: Bearer <token>
```

**Consultar estado de documento**
```
GET /api/v1/documents/{document_id}/status
Authorization: Bearer <token>
```

## License
Este proyecto está licenciado bajo los términos del archivo LICENSE del repositorio.
