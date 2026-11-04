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

La búsqueda y los fragmentos admiten páginas de 1 a 100 elementos y un desplazamiento de 0 a 10 000. El texto de búsqueda admite hasta 256 caracteres. Los límites de `status`, `mime_type`, `source` y `sort` son 32, 128, 64 y 32 caracteres respectivamente. La búsqueda desempata por ID de documento ascendente y los fragmentos se ordenan por su índice.

La selección admite de 1 a 12 documentos, en línea con el límite de RAG Chat. Los IDs de documento y de sesión admiten de 1 a 128 caracteres. Los parámetros de texto rechazan el carácter nulo. La API responde con HTTP 422 ante entradas fuera de estos límites.

La búsqueda devuelve un extracto de hasta 360 caracteres del primer fragmento coincidente, ordenado por índice. Si solo coincide el nombre del archivo, `snippet` es nulo. El detalle y la selección también devuelven `snippet` nulo. La selección conserva el orden de la primera aparición de cada ID, requiere que todos los documentos sean accesibles y estén procesados, y devuelve el ID de sesión recibido.

Los campos `metadata` y `processing_error` se retiraron del contrato público. El estado del documento sigue disponible en `status`. Un documento inexistente o inaccesible devuelve HTTP 404 en detalle y fragmentos. Una selección que incluya cualquiera de esos documentos o un documento sin procesar devuelve HTTP 400.

## Data Models

### DocumentSummaryResponse
- `document_id`: str
- `filename`: str
- `mime_type`: str
- `status`: str
- `chunk_count`: int
- `created_at`: datetime
- `updated_at`: datetime
- `processed_at`: datetime | None
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
Las rutas documentales requieren un token de acceso de AuthServices en `Authorization: Bearer <token>`, con firma RSA válida, `user_id` entero positivo y `exp` entero vigente.

La búsqueda, el detalle, los fragmentos y la selección para el chat aplican la misma regla documental. El acceso puede venir de la propiedad, la administración del tenant, un grupo compartido, una asignación vigente o el rol de superadministrador. Si el documento pertenece a un tenant, el acceso por grupo también exige pertenecer a ese tenant. Las asignaciones canceladas o expiradas dejan de conceder acceso.

Las columnas de propietario y tenant tienen prioridad. Los metadatos históricos sirven como respaldo cuando falta la columna correspondiente. Un documento inaccesible se trata igual que un documento inexistente.

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

Prepara el entorno según el [README principal](../../README.md) y ejecuta desde la raíz del repositorio.

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-search-service
curl http://localhost:8004/api/v1/health/db
```

Compose pasa las variables de búsqueda explícitamente. El chequeo de arranque verifica el acceso a PostgreSQL y a la clave pública JWT. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Configura `SEARCH_CORS_ORIGINS` como arreglo JSON si necesitas otro origen.

Fuera de Compose, instala `requirements.txt` desde este directorio, configura `DATABASE_URL` y `AUTH_JWT_PUBLIC_KEY_PATH` en el entorno o en el `.env` del servicio y ejecuta `python -m uvicorn app.main:app --port 8004`. Para personalizar CORS en este modo, usa `CORS_ORIGINS`.

Con el servicio iniciado, ejecuta las pruebas de permisos, paginación y contrato HTTP sobre PostgreSQL y pgvector. HTTPX es una dependencia exclusiva de pruebas. Los registros sintéticos se revierten al terminar.

```sh
docker compose -f docker/docker-compose.yml cp backend/DocumentSearchServices/tests/test_document_access.py document-search-service:/app/test_document_access.py
docker compose -f docker/docker-compose.yml cp backend/DocumentSearchServices/requirements-test.txt document-search-service:/app/requirements-test.txt
docker compose -f docker/docker-compose.yml exec -T document-search-service python -m pip install -r requirements-test.txt
docker compose -f docker/docker-compose.yml exec -T document-search-service python -m pytest -q test_document_access.py
```

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
