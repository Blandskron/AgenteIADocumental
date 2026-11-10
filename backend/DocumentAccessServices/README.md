# DocumentAccessServices

> Evidencia transversal vigente: [verificación de entrega](../../docs/release/README.md) e [imágenes finales](../../docs/release/IMAGE_AUDIT.json). Runtime Python sin pip/ensurepip; comprobación del grafo durante el build, herramientas en test/audit. Los escaneos fechados anteriores conservan su valor histórico y no describen esta imagen.

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

### Assignments and notifications (Authenticated)

- `GET /api/v1/documents/assigned-to-me`
- `GET /api/v1/documents/managed-by-me`
- `GET /api/v1/documents/notifications`
- `POST /api/v1/documents/notifications/{notification_id}/read`
- `POST /api/v1/documents/{document_id}/assignments`
- `POST /api/v1/documents/assignments/{assignment_id}/accept`
- `POST /api/v1/documents/assignments/{assignment_id}/reject`
- `POST /api/v1/documents/assignments/{assignment_id}/sign`
- `POST /api/v1/documents/assignments/{assignment_id}/cancel`
- `GET /api/v1/documents/assignments/{assignment_id}/events`

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
Las rutas documentales requieren un token de acceso de AuthServices en `Authorization: Bearer <token>`, con firma RSA válida, `user_id` entero positivo y `exp` entero vigente.

Preview y contenido usan la misma regla de lectura que DocumentSearchServices. El acceso puede venir del propietario, un administrador del tenant, un grupo compartido, una asignación vigente como destinatario o asignador, o el rol de superadministrador. Los grupos exigen pertenencia al tenant cuando el documento tiene tenant. Las asignaciones canceladas o expiradas dejan de conceder lectura.

Las columnas de propietario y tenant tienen prioridad sobre los metadatos históricos. Estos sirven como respaldo cuando falta la columna correspondiente. Un documento inaccesible se trata igual que uno inexistente y devuelve HTTP 404.

La descarga comprueba además su permiso específico. El propietario requiere `documents.allow_download` y el destinatario requiere una asignación vigente con `allow_download`. El administrador del tenant y el superadministrador pueden descargar los documentos que administran. El acceso por grupo o como asignador concede lectura. Si existe lectura pero falta permiso de descarga, la API devuelve HTTP 400.

## Asignaciones y transiciones

Las escrituras consultan la cuenta activa, el tenant activo y la membresía vigente en PostgreSQL. El rol activo del token sirve al cliente, pero la autorización de estas operaciones usa el rol actual del tenant del documento. Un superadministrador requiere una cuenta activa con `auth_user.is_superuser`. El destinatario debe tener cuenta y membresía activas en ese mismo tenant. Un destinatario inválido devuelve HTTP 400 una vez autorizado el actor.

El administrador puede asignar documentos de su tenant. El superadministrador puede asignar documentos de tenants activos. Un líder requiere además acceso de lectura al documento. Solo el asignador actual, un administrador de ese tenant o un superadministrador pueden reasignar o cancelar. Una cuenta o membresía deshabilitada pierde inmediatamente estas facultades. Solo el destinatario activo puede aceptar, rechazar o firmar, incluso ante una petición de un administrador.

| Acción | Estados de origen | Requisito |
| --- | --- | --- |
| Aceptar | `PENDING`, `VIEWED` | Destinatario vigente |
| Rechazar | `PENDING`, `VIEWED` | Motivo no vacío |
| Firmar | `PENDING`, `VIEWED`, `ACCEPTED` | Valor de firma no vacío |
| Cancelar | Todos excepto `EXPIRED` | Asignador vigente o administrador autorizado |
| Reasignar | Cualquier estado | Gestor autorizado y destinatario vigente |

Una transición incompatible devuelve HTTP 409. Repetir la misma aceptación, rechazo, firma o cancelación conserva el resultado sin duplicar eventos, notificaciones ni auditoría. Un motivo o firma diferente en una acción ya confirmada devuelve HTTP 409. Repetir una asignación pendiente con el mismo asignador, permisos, vencimiento y metadatos también conserva el resultado.

Cancelar revoca la concesión de acceso y conserva la firma anterior. Reasignar devuelve el estado a `PENDING` y limpia firma, fecha de firma y motivo anteriores, conservando los eventos históricos. La firma representa el valor capturado por la aplicación y no una firma criptográfica. El frontend convierte el vencimiento local a una fecha UTC con zona explícita. `due_at` acepta también fechas sin zona como UTC por compatibilidad con clientes anteriores. El servicio no cambia automáticamente el estado al alcanzar esa fecha.

Cada escritura bloquea primero el documento y después la asignación. Confirma estado, evento, notificación y auditoría en una transacción. Un error revierte todos sus efectos. Los reintentos concurrentes se serializan sobre el documento. La auditoría y las notificaciones conservan el tenant del documento, aunque el tenant activo del token sea otro. Marcar una notificación como leída requiere su destinatario activo y conserva `read_at` al reintentar.

## Entradas, páginas y errores

Los identificadores de ruta admiten entre 1 y 128 caracteres sin controles. El destinatario se envía como texto decimal positivo, sin ceros iniciales, con hasta 19 dígitos y debe corresponder a una cuenta vigente. Los motivos admiten hasta 2000 caracteres y los valores de firma hasta 4096, sin bytes nulos. Los cuerpos de asignación y acción rechazan campos desconocidos.

Los metadatos deben ser un objeto JSON finito de hasta 16.384 bytes UTF-8 al serializarlo sin espacios, con hasta 16 niveles. Se rechazan bytes nulos en claves y valores. Las peticiones POST, PUT y PATCH tienen un presupuesto de 65.536 bytes de cuerpo, contado sobre los bytes recibidos incluso si se omite o altera `Content-Length`. Estos límites validan entradas nuevas; los registros históricos conservan su formato de lectura.

`assigned-to-me`, `managed-by-me`, `notifications` y `assignments/{assignment_id}/events` devuelven un objeto paginado. Esta respuesta sustituye al arreglo anterior y requiere actualizar el frontend junto con el backend.

```json
{"items": [], "limit": 50, "offset": 0, "has_more": false}
```

Usa `limit` de 1 a 100, con 50 por defecto, y `offset` de 0 a 100.000, con 0 por defecto. La siguiente página comienza en `offset + items.length`. Las asignaciones y notificaciones se ordenan por fecha de creación descendente e ID descendente. Los eventos usan fecha e ID ascendentes. La consulta recupera como máximo `limit + 1` filas para calcular `has_more`, sin contar todo el historial. Las páginas pertenecen al actor autorizado y `notifications` admite `status=UNREAD`, `status=READ` o `status=ARCHIVED`.

El orden es estable para un conjunto sin cambios. Las páginas por offset no representan una instantánea frente a inserciones o eliminaciones concurrentes. Refrescar vuelve a la primera página. El frontend ofrece **Cargar más**, evita duplicados por ID y muestra contadores de registros cargados. Después de mutaciones o un conflicto HTTP 409 vuelve a consultar el estado.

HTTP 422 indica una entrada o parámetro inválido; HTTP 413 indica un cuerpo o contenido demasiado grande; HTTP 400 conserva las reglas de negocio, incluido destinatario inválido o motivo obligatorio; HTTP 409 indica conflicto de estado. Los errores 422 incluyen `detail` con `loc`, `msg` y `type`, sin reflejar valores enviados ni firmas. El frontend los convierte en texto legible. Consultar eventos de una asignación inexistente o ajena devuelve HTTP 404; una asignación visible sin eventos devuelve una página vacía.

## Archivos y contenido

El almacenamiento admite rutas relativas, rutas absolutas dentro del directorio configurado y URI `file:` locales. Las URI pueden omitir la autoridad o usar `localhost`. Se decodifican los nombres con espacios y caracteres Unicode. Las rutas fuera del almacenamiento, autoridades remotas, controles y bucles de enlaces devuelven HTTP 400. Las URI con consultas o fragmentos también se rechazan. Los enlaces simbólicos deben terminar dentro del almacenamiento. Un archivo ausente devuelve HTTP 404.

Preview admite `application/pdf`, `text/plain`, `image/png`, `image/jpeg` e `image/tiff`. Los demás tipos devuelven HTTP 415 en preview. La descarga comprueba su permiso y sirve los tipos desconocidos como `application/octet-stream`. Las respuestas de archivo usan `X-Content-Type-Options: nosniff` y `Cache-Control: private, no-store`, conservan Range y preparan un nombre de archivo sin directorios ni controles para `Content-Disposition`. La auditoría de descarga se registra después de resolver un archivo existente.

`content` devuelve hasta `max_chunks` fragmentos, de 1 a 2000, con 500 por defecto. El presupuesto es de 2.000.000 de caracteres recuperados, incluidos los espacios descartados al ensamblar y los separadores entre fragmentos. Si se supera el presupuesto, la API devuelve HTTP 413. La consulta acota cada fragmento en SQL y los procesa con un cursor de una fila para limitar la memoria usada por registros históricos.

## Borrado y recuperación

El propietario, el administrador del tenant correspondiente y el superadministrador pueden borrar. Las columnas canónicas tienen prioridad sobre los metadatos históricos. Los demás actores reciben HTTP 404, incluidos quienes solo pueden leer por grupo o asignación.

PostgreSQL bloquea la fila del documento y confirma en una transacción su eliminación, las relaciones dependientes, la auditoría `DOCUMENT_DELETED` y un registro en `document_deletions`. La limpieza del archivo empieza después de esa confirmación. Una interrupción deja el trabajo persistido para recuperarlo.

HTTP 200 con `deleted: true` indica que el documento fue retirado de la plataforma. `file_deleted: true` indica que esa limpieza retiró la entrada del archivo. Puede ser falso si el archivo ya faltaba, está compartido o la limpieza sigue pendiente. Los registros de borrado se conservan para responder reintentos autorizados sin duplicar la auditoría.

El servicio recupera trabajos al arrancar y revisa hasta 20 pendientes cada 30 segundos. Un fallo del sistema de archivos o una referencia compartida difiere el siguiente intento 60 segundos. `SKIP LOCKED` permite que varios procesos compartan la cola. Una nueva petición DELETE autorizada también puede reintentar la limpieza.

La limpieza contrasta las referencias vigentes, incluidas URI, enlaces simbólicos y enlaces duros. Conserva archivos que otros documentos todavía usan. Para borrar un enlace simbólico retira su entrada y conserva el destino. La comprobación recorre rutas distintas con un cursor y su coste crece con la cantidad de rutas de la biblioteca.

Compose aplica [el esquema de la cola](../../scripts/database/schemas/012_document_deletions.sql) mediante `database-schema`, tanto en bases nuevas como existentes. `health/db` comprueba también esa tabla. Para revisar trabajos diferidos, ejecuta desde la raíz.

```sh
docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -c "SELECT document_id, attempts, last_error, next_attempt_at FROM document_deletions WHERE completed_at IS NULL ORDER BY next_attempt_at;"
```

`last_error` conserva el tipo de error o `SharedReference`. Las rutas inválidas quedan pendientes y requieren corregir la ubicación almacenada antes de poder completar su limpieza.

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

Prepara el entorno según el [README principal](../../README.md) y ejecuta desde la raíz del repositorio.

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-access-service
curl http://localhost:8005/api/v1/health/db
```

Compose pasa explícitamente las variables del servicio. El chequeo de arranque verifica PostgreSQL, las funciones de autorización, la clave pública JWT y la existencia del directorio de documentos. `health/db` devuelve HTTP 503 sin detalles de conexión si la base o las funciones no están disponibles. CORS admite `http://localhost:3000` y `http://127.0.0.1:3000` por defecto. Configura `ACCESS_CORS_ORIGINS` como arreglo JSON para otros orígenes.

`access-db-role` se ejecuta después del esquema y de AuthServices. Provisiona y comprueba el rol `document_access_runtime` de forma repetible. El servicio recibe una URL sin contraseña y `PGPASSWORD` desde `ACCESS_DB_PASSWORD`. Las credenciales administrativas quedan en los trabajos de provisionamiento y en las fixtures de pruebas.

| Recurso | Permisos de ejecución |
| --- | --- |
| Documentos | Lectura y borrado. `UPDATE(document_id)` permite adquirir el bloqueo de fila requerido por PostgreSQL. |
| Fragmentos | Lectura de ID documental, índice y texto, sin acceso al vector. |
| Asignaciones | Lectura, inserción y actualización de campos de gestión y estado. |
| Eventos | Lectura e inserción, sin edición ni borrado directo. |
| Notificaciones | Lectura, inserción y actualización del estado de lectura y sus fechas. |
| Cola de borrado | Lectura, inserción y actualización de resultados e intentos. |
| Auditoría | Inserción y lectura del ID y fecha que devuelve el ORM. |
| Usuarios y membresías | Tres funciones de consulta y bloqueo, sin acceso directo a las tablas ni contraseñas. |

Las funciones `access_active_user`, `access_active_tenant` y `access_active_membership` mantienen los bloqueos compartidos hasta terminar la transacción. Su propietario `document_access_authorizer` no tiene login ni membresías. Usan nombres de tabla cualificados, un `search_path` fijo y ejecución revocada a `PUBLIC`. Esto conserva las comprobaciones vigentes sin conceder edición de cuentas o membresías al servicio. Sigue las recomendaciones de PostgreSQL para [funciones con permisos del propietario](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).

La imagen final ejecuta como UID/GID `10004:10004`, sin capacidades adicionales ni elevación de privilegios. Las herramientas de pruebas y de auditoría viven en etapas separadas. En Linux, prepara el directorio `documents` con el propietario utilizado por la ingesta y configura ambos servicios con esos mismos UID/GID. `ACCESS_UID` y `ACCESS_GID` permiten ajustar el usuario de Compose. Leer requiere acceso a los archivos; retirar una entrada requiere escritura y recorrido de su directorio padre. El servicio no cambia permisos ni propietarios del almacenamiento al arrancar.

Para rotar la contraseña local, cambia `ACCESS_DB_PASSWORD` en `.env`, ejecuta `docker compose -f docker/docker-compose.yml run --rm access-db-role` y recrea el servicio con `up -d --force-recreate document-access-service`. Puedes comprobar el contrato SQL desde PowerShell.

```powershell
Get-Content scripts/database/access/verify_role.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
```

Fuera de Compose, instala `requirements.txt` desde este directorio y configura `DATABASE_URL`, `PGPASSWORD`, `AUTH_JWT_PUBLIC_KEY_PATH` y `DOCUMENT_STORAGE_BASE_PATH` en el entorno o en el `.env` del servicio. Provisiona previamente el rol con `scripts/database/access/provision_role.sql` usando una sesión administrativa de psql y `ACCESS_DB_PASSWORD` en su entorno. Ejecuta `python -m uvicorn app.main:app --port 8005`. En este modo, configura CORS con `CORS_ORIGINS`.

Consulta [AGENTS.md](AGENTS.md) para colaborar y la [verificación de entrega](../../docs/release/README.md) para evidencia transversal, alcance y avisos.

## Pruebas

Con el servicio iniciado, ejecuta las pruebas HTTP con JWT y documentos sintéticos sobre PostgreSQL y pgvector.

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps access-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps access-tests ruff check --no-cache app tests
docker compose -f docker/docker-compose.yml run --build --rm --no-deps access-audit
```

Desde `frontend`, `npm test` verifica la adaptación de páginas, fechas y errores HTTP. CI ejecuta estas pruebas antes de compilar la interfaz.

Las fixtures usan `ACCESS_TEST_DATABASE_URL` para preparar e inspeccionar datos sintéticos. Las operaciones de aplicación usan el rol de ejecución, incluidas las pruebas HTTP, recuperación y concurrencia. Los casos con savepoints revierten sus registros y los casos confirmados usan IDs únicos y los retiran al terminar. Los archivos de prueba se crean en un directorio temporal. CI comprueba el provisionamiento repetido, los permisos negativos, el usuario de la imagen, la ausencia de herramientas de prueba, Ruff y la auditoría Python.

## Estado y seguimiento operativo

El cierre funcional de los incrementos ACCESS-001 a ACCESS-007 cubre permisos, archivos, contenido, borrado recuperable, asignaciones atómicas y páginas acotadas. Se comprobó el arranque con volúmenes nuevos y la retirada automática de un archivo sintético por el proceso sin privilegios. El rol restringe recursos del servicio; el aislamiento por usuario y tenant sigue siendo responsabilidad de las reglas de aplicación probadas, sin RLS por usuario de la API.

El 5 de noviembre de 2026, `pip-audit` 2.10.1 no reportó vulnerabilidades conocidas en el inventario completo de Python de la imagen de ejecución. El objetivo `access-audit` congela ese inventario antes de instalar el auditor, para incluir dependencias transitivas sin confundirlas con las herramientas de auditoría.

Trivy 0.74.0 examinó los paquetes del sistema de la imagen `sha256:341af67dbe506c6caae0beff102eb0c3444060fb20225e2fa3a5c78d16c422b4`, basada en Debian 13.7. Reportó 46 coincidencias altas por paquete, correspondientes a 10 CVE distintos, sin críticos ni versiones corregidas indicadas en el resultado. Los CVE fueron CVE-2025-69720, CVE-2026-119373, CVE-2026-16742, CVE-2026-54369, CVE-2026-76642, CVE-2026-76844, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 y CVE-2026-9538. La verificación de entrega conserva los avisos de la imagen base y su disposición. Estos avisos requieren reevaluación al reconstruir y no equivalen a una explotación validada de las rutas del servicio.

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
