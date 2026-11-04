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
- `GET /api/v1/health/ai` — Verifica la configuración del proveedor de AI

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
Todos los endpoints (excepto health checks) requieren un JWT válido en el header `Authorization: Bearer <token>`. El token se valida con la clave pública RSA configurada y debe tener `token_type: access`.

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
1. Instala dependencias: `pip install -r requirements.txt`
2. Configura variables de entorno o edita el archivo de configuración
3. Ejecuta con Uvicorn: `uvicorn app.main:app --reload`
4. O usa Docker: `docker build -t rag-document-chat-services . && docker run ...`

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
