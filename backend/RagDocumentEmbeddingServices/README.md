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

La carga admite archivos de hasta 20 MiB y metadatos JSON de hasta 64 KiB. El cuerpo multipart tiene un margen adicional de 128 KiB para sus campos y cabeceras. La API devuelve `413` cuando se supera alguno de esos límites.

La extracción admite hasta 200 páginas de PDF, 1024 entradas y 64 MiB descomprimidos por DOCX, imágenes de hasta 16 megapíxeles y un máximo de 20 segundos por operación OCR. El texto extraído se limita a un millón de caracteres. Los límites de extracción devuelven `422`.

El procesamiento solo lee archivos bajo `DOCUMENT_STORAGE_BASE_PATH`. Se admiten rutas relativas y rutas locales históricas que resuelvan dentro de ese directorio. Los límites de extracción también se aplican al reindexar archivos existentes. Si falla el registro inicial, se elimina el archivo recién escrito. Si falla el procesamiento después del registro, el archivo se conserva para poder reintentar.

La ingesta genera vectores normalizados de 384 dimensiones en CPU, en lotes de hasta 32 fragmentos y con un máximo de 2048 fragmentos por documento. Usa los mismos pesos Safetensors que el chat y el prefijo `passage:` para indexar. Los documentos sin texto extraíble y los vectores inválidos se rechazan antes de reemplazar el índice. [Revisión fijada del modelo](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3).

Durante la indexación, las consultas siguen viendo el último estado confirmado. Un intento simultáneo sobre el mismo documento devuelve `409`. Al terminar, los nuevos fragmentos y el estado `PROCESSED` se confirman juntos. Si falla una reindexación, se mantiene el índice anterior. Una primera indexación fallida queda como `FAILED`.

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

Compose provisiona el rol `embedding_runtime` después del esquema. El servicio puede registrar documentos, actualizar su estado y reemplazar sus fragmentos. Para cambiar su contraseña local, configura `EMBEDDING_DB_PASSWORD` y vuelve a ejecutar el comando de arranque.

La imagen usa UID y GID 10004 por defecto. El directorio compartido `documents` debe admitir escritura por parte del usuario del contenedor. En Linux, crea el directorio con `mkdir -p documents` y configura `EMBEDDING_UID` y `EMBEDDING_GID` en `.env` con los valores de `id -u` e `id -g` de un usuario no root que pueda escribir allí. El chequeo de arranque comprueba ese permiso.

Con el servicio levantado, ejecuta la suite en su imagen de pruebas. Los registros sintéticos se preparan con credenciales separadas y la ingesta se prueba con el rol de ejecución.

```sh
docker compose -f docker/docker-compose.yml run --build --rm embedding-tests
```

### Verificación de la imagen

Reconstruye con `docker compose -f docker/docker-compose.yml build --pull rag-document-embedding-service`. Audita las versiones instaladas con `pip-audit` a partir de `pip list --format=freeze` dentro de la imagen. Para revisar también Debian y las dependencias empaquetadas, ejecuta `trivy image --scanners vuln --severity HIGH,CRITICAL docker-rag-document-embedding-service`.

El 4 de noviembre de 2026, `pip-audit` no reportó avisos para los paquetes Python instalados en la imagen `sha256:6e043fa1cb26203d36f4e29f7f7fc8e372c6cf5d00840aefd2207e01ecee8be5`. Trivy 0.74.0, sobre el inventario `dpkg` de la imagen, reportó 31 CVE altos y un CVE crítico en Debian 13.7 sin versiones corregidas indicadas para esa distribución.

El análisis completo del archivo de imagen agotó su tiempo de ejecución. La evidencia anterior cubre el inventario de Debian y las versiones Python instaladas.

El hallazgo crítico de Trivy es CVE-2026-6653 en la biblioteca `libxml2` del sistema, enlazada por Tesseract. Debian confirma que la versión instalada sigue afectada en Trixie y clasifica el problema como menor. La extensión Python `lxml` reporta una copia separada de libxml2 2.14.6. [Seguimiento de Debian](https://security-tracker.debian.org/tracker/CVE-2026-6653).

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
