# RagDocumentChatServices

> Evidencia transversal fechada: [verificación de entrega](../../../docs/release/README.md). Runtime Python sin pip/ensurepip; comprobación del grafo durante el build, herramientas en test/audit. Los escaneos fechados anteriores conservan su valor histórico y no describen esta imagen.

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

La pregunta admite hasta 4096 caracteres. La sesión y cada ID documental admiten hasta 128 caracteres, con un máximo de 12 IDs por consulta. Los valores fuera de esos límites devuelven `422`.

El modelo recibe hasta 24 fragmentos de 1200 caracteres cada uno y las ocho preguntas previas más recientes de la sesión, recortadas a 1000 caracteres cada una. Los resúmenes alternan fragmentos entre documentos y las fuentes de la respuesta corresponden al contexto enviado. `VECTOR_SEARCH_LIMIT` admite valores de 1 a 24.

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

Con un ID de sesión, el servicio guarda la pregunta y la respuesta juntas después de generar la respuesta. Si falla la recuperación o la generación, devuelve la respuesta de contingencia sin incorporar ese intento al historial del modelo.

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
Desde la raíz, prepara el entorno según el [README principal](../../../README.md), configura `GROQ_API_KEY` para generar respuestas y arranca el servicio:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait rag-document-chat-service
curl http://localhost:8002/api/v1/health/db
curl http://localhost:8002/api/v1/health/ai
```

Compose pasa las variables de Groq y búsqueda de forma explícita. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Para otro origen de desarrollo, configura `RAG_CHAT_CORS_ORIGINS` como arreglo JSON. En ejecución directa, instala `requirements.txt` desde este directorio, configura `DATABASE_URL` y `AUTH_JWT_PUBLIC_KEY_PATH` y ejecuta `python -m uvicorn app.main:app --port 8002`. La aplicación lee el entorno del proceso y el `.env` de este directorio.

Compose provisiona `rag_chat_runtime` después de preparar el esquema. El rol puede insertar turnos y leer las columnas necesarias para recuperar fragmentos y comprobar permisos. Para cambiar la contraseña local, configura `RAG_CHAT_DB_PASSWORD` y vuelve a ejecutar el comando de arranque. Fuera de Compose, usa ese rol en `DATABASE_URL`. El contenedor corre como UID 10003 y su sonda de arranque comprueba PostgreSQL y la clave pública.

Ejecuta las pruebas con el stack local. La imagen de pruebas prepara registros sintéticos con una conexión separada, cambia al rol de ejecución para las consultas del servicio y revierte los datos al terminar. Los proveedores se simulan.

```sh
docker compose -f docker/docker-compose.yml run --build --rm rag-chat-tests
```

Las pruebas del adaptador Groq usan el cliente HTTP real con transporte simulado y se ejecutan en CI sin credenciales. Desde este directorio, con las dependencias instaladas, ejecuta `python -m pytest -q tests/test_groq_provider.py`. Cada consulta hace un solo intento de generación con el tiempo de espera configurado. Una respuesta vacía, un error del proveedor o un timeout activa la respuesta de contingencia del chat.

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

La búsqueda vectorial usa PyTorch CPU y pesos Safetensors. La primera consulta vectorial descarga el modelo a la caché del usuario del contenedor. Para probar el chat completo, indexa un documento de ejemplo con el servicio de ingesta. [Revisión fijada de multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3).

### Verificación de la imagen

Reconstruye con `docker compose -f docker/docker-compose.yml build --pull rag-document-chat-service`. La [auditoría transversal vigente](../../../docs/release/README.md) captura el inventario con `importlib.metadata` y escanea la imagen inmutable. El grafo se valida durante el build; runtime ya no incluye `pip` ni `ensurepip`. Los resultados siguientes corresponden al artefacto histórico del 4 de noviembre, no a la entrega actual.

El 4 de noviembre de 2026, `pip-audit` no reportó avisos para los paquetes instalados de la imagen `sha256:d5235e0f6b18719a4d0318e784ecb414adad44f06da927c91e2c855856e52d66`. Trivy 0.74.0 reportó nueve CVE altos únicos en Debian 13.7, sin versiones corregidas indicadas.

Trivy también reportó CVE-2025-47273 para `setuptools 70.3.0`, versión declarada por los metadatos internos de pip. La imagen instala `setuptools 84.2.1`. La copia interna de pip incluye `pkg_resources` y la inspección del paquete de pip no encontró `package_index`, el módulo afectado. [Aviso de PyPA](https://github.com/pypa/advisory-database/blob/main/vulns/setuptools/PYSEC-2025-49.yaml).

## Identidad vigente

Antes de autorizar, el servicio valida el JWT y consulta el perfil actual de Auth en `AUTH_IDENTITY_URL` (Compose: `http://auth-service:8001/api/users/me/`; ejecución directa: loopback 8001). Usa grupos, membresías y privilegios actuales, incluidos sus alias heredados. Auth rechaza cuentas inactivas, eliminadas o con contraseña cambiada. Error de autenticación: 401; Auth indisponible o respuesta inválida: 503. No hay caché, proxies de entorno ni redirecciones del Bearer. El timeout de socket es de cinco segundos. Las pruebas unitarias simulan Auth; la verificación transversal comprueba revocación con Auth/PostgreSQL reales.
