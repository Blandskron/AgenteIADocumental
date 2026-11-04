# RagDocumentChatServices

## Overview
RagDocumentChatServices es un microservicio basado en FastAPI que permite realizar chat conversacional con contexto recuperado de documentos mediante técnicas RAG (Retrieval-Augmented Generation). Integra búsqueda semántica de fragmentos relevantes y generación de respuestas con LLM, soportando autenticación JWT y persistencia en PostgreSQL.

## Features
- Endpoint de chat con contexto documental (RAG)
- Recuperación semántica de fragmentos relevantes (vector search)
- Generación de respuestas con LLM
- Soporte para múltiples documentos y sesiones
- Endpoints autenticados vía JWT
- Health checks (servicio, base de datos, AI)
- CORS para integración frontend

## API Endpoints

### Health
- `GET /api/v1/health` — Verifica el estado del servicio
- `GET /api/v1/health/db` — Verifica la conectividad con la base de datos
- `GET /api/v1/health/ai` — Devuelve `200` si hay una clave de Groq configurada o `503` si falta. La sonda no hace solicitudes al proveedor.

### Chat (Authenticated)
- `POST /api/v1/chat/ask` — Realiza una pregunta al chat con contexto documental
  - **Body:**
    - `question`: str (requerido)
    - `session_id`: str | null (opcional)
    - `document_ids`: list[str] (opcional)
  - **Response:**
    - `answer`: str
    - `sources`: lista de fragmentos relevantes (document_id, chunk_id, content, score, filename)

## Data Models

### ChatAskRequest
- `question`: str
- `session_id`: str | None
- `document_ids`: list[str]

### ChatAskResponse
- `answer`: str
- `sources`: list[ChatSourceResponse]

### ChatSourceResponse
- `document_id`: str
- `chunk_id`: str
- `content`: str
- `score`: float
- `filename`: str | None

## Authentication
El endpoint de chat requiere un token de acceso de AuthServices en `Authorization: Bearer <token>`, con firma RSA válida, `user_id` entero positivo y `exp` entero vigente. El usuario también debe tener el permiso activo `use_chat`, acceso global o el rol de superadministrador.

La búsqueda semántica y los resúmenes aplican el mismo filtro documental antes de enviar fragmentos a Groq. Las asignaciones canceladas o expiradas dejan de conceder acceso. El contexto de historial incluye las preguntas previas del mismo usuario y sesión. Las respuestas anteriores se conservan en la base, pero se excluyen del contexto porque pueden contener datos de documentos cuyo acceso cambió.

## Architecture
- **FastAPI** para la capa API
- **SQLAlchemy** para ORM/acceso a base de datos
- **PostgreSQL** como base de datos
- **Pydantic** para validación de requests/responses
- **Docker** para contenerización
- **CORS** habilitado para integración frontend
- **Vector search** para recuperación semántica
- **LLM provider** para generación de respuestas

## Project Structure
- `app/main.py`: Setup de FastAPI, middleware, manejo de errores
- `app/interfaces/api/router.py`: Registro de rutas y endpoints
- `app/interfaces/api/v1/routes/`: Implementación de endpoints
- `app/application/chat/use_cases/`: Lógica de negocio de chat
- `app/application/embeddings/use_cases/`: Recuperación semántica
- `app/domain/chat/`: Entidades de chat
- `app/domain/embeddings/`: Entidades de búsqueda semántica
- `app/infrastructure/database/`: Modelos, repositorios, conexión a BD
- `app/config/`: Configuración, seguridad, logging
- `app/shared/`: Clases de error compartidas

## Running the Service
Desde la raíz, prepara el entorno según el [README principal](../../README.md), configura `GROQ_API_KEY` para generar respuestas y arranca el servicio:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait rag-document-chat-service
curl http://localhost:8002/api/v1/health/db
curl http://localhost:8002/api/v1/health/ai
```

Compose pasa las variables de Groq y búsqueda de forma explícita. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Para otro origen de desarrollo, configura `RAG_CHAT_CORS_ORIGINS` como arreglo JSON. En ejecución directa, instala `requirements.txt` desde este directorio, configura `DATABASE_URL` y `AUTH_JWT_PUBLIC_KEY_PATH` y ejecuta `python -m uvicorn app.main:app --port 8002`. La aplicación lee el entorno del proceso y el `.env` de este directorio.

Con el stack local iniciado, prueba la autenticación y los permisos con PostgreSQL y pgvector. Los registros sintéticos se revierten al terminar y los proveedores de embeddings y respuestas se simulan.

```sh
docker compose -f docker/docker-compose.yml cp backend/RagDocumentChatServices/tests/test_document_access.py rag-document-chat-service:/app/test_document_access.py
docker compose -f docker/docker-compose.yml exec -T rag-document-chat-service python -m pytest -q test_document_access.py
```

## Example Requests

**Pregunta al chat con contexto documental**
```json
POST /api/v1/chat/ask
{
  "question": "¿Cuál es el objetivo del contrato?",
  "session_id": "abc123",
  "document_ids": ["doc1", "doc2"]
}
```

## License
Este proyecto está licenciado bajo los términos del archivo LICENSE del repositorio.
# Generación con Groq

Configura `GROQ_API_KEY` en el `.env` local. `GROQ_CHAT_MODEL` usa `openai/gpt-oss-20b` por defecto. Estas variables son del backend.

La búsqueda vectorial genera embeddings localmente en CPU. Para probar el chat completo, indexa un documento de ejemplo con el servicio de ingesta.
