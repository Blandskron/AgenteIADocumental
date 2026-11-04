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
Todos los endpoints (excepto health checks) requieren un JWT válido en el header `Authorization: Bearer <token>`. El token se valida con la clave pública RSA configurada y debe tener `token_type: access`.

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
1. Instala dependencias: `pip install -r requirements.txt`
2. Configura variables de entorno o edita el archivo de configuración
3. Ejecuta con Uvicorn: `uvicorn app.main:app --reload`
4. O usa Docker: `docker build -t rag-document-embedding-services . && docker run ...`

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
