# DocumentSearchServices

## Overview
DocumentSearchServices es un microservicio basado en FastAPI que proporciona endpoints para la búsqueda, consulta y selección de documentos y sus fragmentos (chunks). Permite búsquedas avanzadas, obtención de detalles, paginación de resultados y selección de documentos para contexto de chat, integrándose en una arquitectura de microservicios con autenticación JWT y persistencia en PostgreSQL.

## Features
- Búsqueda avanzada de documentos con filtros y paginación
- Consulta de detalles de documentos
- Acceso a fragmentos (chunks) de documentos
- Selección de documentos para contexto de chat
- Endpoints autenticados vía JWT
- Health checks
- CORS para integración frontend

## API Endpoints

### Health
- `GET /api/v1/health` — Verifica el estado del servicio
- `GET /api/v1/health/db` — Verifica la conectividad con la base de datos

### Documentos (Authenticated)
- `GET /api/v1/documents/search` — Busca documentos (parámetros: q, status, mime_type, source, limit, offset, sort)
- `GET /api/v1/documents/{document_id}` — Obtiene detalles de un documento
- `GET /api/v1/documents/{document_id}/chunks` — Lista fragmentos (chunks) de un documento (parámetros: q, limit, offset)
- `POST /api/v1/documents/chat-selection` — Selecciona documentos para contexto de chat

## Data Models

### DocumentSummaryResponse
- `document_id`: str
- `filename`: str
- `mime_type`: str
- `status`: str
- `metadata`: dict
- `chunk_count`: int
- `created_at`: datetime
- `updated_at`: datetime
- `processed_at`: datetime | None
- `processing_error`: str | None
- `snippet`: str | None

### DocumentSearchResponse
- `items`: list[DocumentSummaryResponse]
- `total`: int
- `limit`: int
- `offset`: int

### DocumentChunkResponse
- `chunk_id`: str
- `document_id`: str
- `chunk_index`: int
- `content`: str
- `metadata`: dict
- `created_at`: datetime

### DocumentChunksResponse
- `items`: list[DocumentChunkResponse]
- `total`: int
- `limit`: int
- `offset`: int

### ChatSelectionRequest
- `document_ids`: list[str]
- `session_id`: str | None

### ChatSelectionResponse
- `session_id`: str | None
- `documents`: list[DocumentSummaryResponse]
- `suggested_prompt`: str

## Authentication
Todos los endpoints (excepto health checks) requieren un JWT válido en el header `Authorization: Bearer <token>`. El token se valida con la clave pública RSA configurada y debe tener `token_type: access`.

## Architecture
- **FastAPI** para la capa API
- **SQLAlchemy** para ORM/acceso a base de datos
- **PostgreSQL** como base de datos
- **Pydantic** para validación de requests/responses
- **Docker** para contenerización
- **CORS** habilitado para integración frontend

## Project Structure
- `app/main.py`: Setup de FastAPI, middleware, manejo de errores
- `app/interfaces/api/router.py`: Registro de rutas y endpoints
- `app/interfaces/api/v1/routes/`: Implementación de endpoints
- `app/application/documents/use_cases/`: Lógica de negocio
- `app/domain/documents/`: Entidades y excepciones de dominio
- `app/infrastructure/database/`: Modelos, repositorios, conexión a BD
- `app/config/`: Configuración, seguridad, logging
- `app/shared/`: Clases de error compartidas

## Running the Service
1. Instala dependencias: `pip install -r requirements.txt`
2. Configura variables de entorno o edita el archivo de configuración
3. Ejecuta con Uvicorn: `uvicorn app.main:app --reload`
4. O usa Docker: `docker build -t document-search-services . && docker run ...`

## Example Requests

**Buscar documentos**
```
GET /api/v1/documents/search?q=contrato&limit=10
Authorization: Bearer <token>
```

**Obtener detalles de un documento**
```
GET /api/v1/documents/{document_id}
Authorization: Bearer <token>
```

**Seleccionar documentos para chat**
```
POST /api/v1/documents/chat-selection
{
  "document_ids": ["doc1", "doc2"],
  "session_id": "abc123"
}
Authorization: Bearer <token>
```

## License
Este proyecto está licenciado bajo los términos del archivo LICENSE del repositorio.
