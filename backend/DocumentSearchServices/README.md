# DocumentSearchServices

> Evidencia transversal vigente: [verificación de entrega](../../docs/release/README.md) e [imágenes finales](../../docs/release/IMAGE_AUDIT.json). Runtime Python sin pip/ensurepip; comprobación del grafo durante el build, herramientas en test/audit. Los escaneos fechados anteriores conservan su valor histórico y no describen esta imagen.

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

Después de aplicar el esquema, Compose aprovisiona `document_search_runtime` mediante `search-db-role`. El rol solo puede leer las columnas necesarias de documentos, fragmentos y asignaciones. Los permisos por documento se aplican en el servicio. Define `SEARCH_DB_PASSWORD` en `.env` para cambiar la contraseña local. El contenedor se ejecuta con UID y GID 10005.

Fuera de Compose, provisiona el rol con [el script SQL](../../scripts/database/search/provision_role.sql) usando una cuenta administrativa y `SEARCH_DB_PASSWORD` en el entorno de `psql`. Instala `requirements.txt` desde este directorio, configura `DATABASE_URL` para el rol de lectura y `AUTH_JWT_PUBLIC_KEY_PATH`, y ejecuta `python -m uvicorn app.main:app --port 8004`. Para personalizar CORS en este modo, usa `CORS_ORIGINS`.

Con el servicio iniciado, ejecuta las pruebas de permisos, paginación y contrato HTTP sobre PostgreSQL y pgvector. La imagen de pruebas incluye HTTPX, pytest y Ruff. Las pruebas preparan registros sintéticos en una transacción, ejecutan las consultas con el rol de lectura y revierten los cambios al terminar.

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps search-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps search-tests ruff check --no-cache app tests
```

## Verificación de la imagen

El 5 de noviembre de 2026 se validó un arranque con volúmenes nuevos, el aprovisionamiento repetido del rol, las comprobaciones SQL y 26 pruebas sobre PostgreSQL con pgvector. Las pruebas incluyen conexiones reales como `document_search_runtime` y verifican que se rechacen lecturas internas, escrituras y creación de tablas. CI repite las comprobaciones del rol, el contrato HTTP, Ruff, el usuario del contenedor y `pip check`.

`pip-audit` no reportó avisos para las versiones Python instaladas en la imagen `sha256:c70c5369e4013879b46b11a86e792119ad080f4df6b76c3d6bc68f555cdd2a43`. Trivy 0.74.0 reportó 46 coincidencias que corresponden a diez CVE altos únicos en Debian 13.7, sin versiones corregidas indicadas por el escáner. Quedan en seguimiento al actualizar la imagen base.

Trivy también reportó CVE-2025-47273 por `setuptools==70.3.0` en `pip/_vendor/vendor.txt`. La copia interna de pip 26.3 incluye `pkg_resources`. La inspección no encontró el módulo `package_index` al que corresponde el aviso. [Aviso de setuptools](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf).

Reconstruye con `docker compose -f docker/docker-compose.yml build --pull document-search-service`. La [auditoría transversal vigente](../../docs/release/README.md) captura el inventario con `importlib.metadata` y escanea la imagen inmutable. El grafo se valida durante el build; runtime ya no incluye `pip` ni `ensurepip`. Los resultados de los párrafos siguientes son históricos, no el estado del artefacto actual.

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

## Identidad vigente

Antes de autorizar, el servicio valida el JWT y consulta el perfil actual de Auth en `AUTH_IDENTITY_URL` (Compose: `http://auth-service:8001/api/users/me/`; ejecución directa: loopback 8001). Usa grupos, membresías y privilegios actuales, incluidos sus alias heredados. Auth rechaza cuentas inactivas, eliminadas o con contraseña cambiada. Error de autenticación: 401; Auth indisponible o respuesta inválida: 503. No hay caché, proxies de entorno ni redirecciones del Bearer. El timeout de socket es de cinco segundos. Las pruebas unitarias simulan Auth; la verificación transversal comprueba revocación con Auth/PostgreSQL reales.
