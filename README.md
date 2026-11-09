# Blandskron Documental

Proyecto de portafolio de Blandskron. Carga un documento, búscalo, haz una pregunta sobre su contenido y exporta la respuesta a PDF.

La ingesta extrae texto y genera embeddings locales en CPU. El chat recupera fragmentos de PostgreSQL con pgvector según los permisos del usuario y envía el contexto a Groq para redactar una respuesta con fuentes.

```text
Documento → extracción → embeddings → PostgreSQL / pgvector
Pregunta → búsqueda con permisos → contexto → Groq → respuesta y PDF
```

Google Drive es una integración opcional que requiere configurar OAuth. La conexión usa PKCE S256 e intentos por pestaña; la desconexión confirma la revocación o muestra un estado pendiente. API, esquema y web deben desplegarse juntos. [Operación y rotación de claves](backend/GoogleDriveImportServices/README.md#oauth-y-credenciales-drive-004). Para la demo basta con un archivo de texto o PDF sintético.

Drive arranca deshabilitado (`GOOGLE_DRIVE_ENABLED=false`), sin credenciales Google. Mantiene disponibles health e historial autorizado; las operaciones de proveedor devuelven 503. Su runtime usa `drive_runtime` y requiere aprovisionar `drive-db-role` con `DRIVE_DB_PASSWORD`. [Configuración, permisos y actualización](backend/GoogleDriveImportServices/README.md#operación-drive-002003).

El perfil se guarda con control de versión: si otra sesión lo modificó, conserva tu formulario y ofrece recargar el perfil antes de guardar de nuevo. Renovar la sesión o subir una foto conserva el borrador de contacto; cambiar de cuenta o tenant reinicia el editor. El correo de contacto se edita por separado de la identidad y los permisos se muestran para el tenant activo. La actualización requiere aplicar el esquema y reconstruir la web junto al servicio. [Actualizar Profile](backend/ProfileServices/README.md#actualizar-una-instalación-existente) y [pruebas web](backend/ProfileServices/README.md#sesión-y-edición-web).

Exportar guarda una instantánea enviada por el cliente en PDF de hasta 20 páginas/1 MiB, con Unicode latino/griego/cirílico y persistencia transaccional. La actualización requiere aplicar el esquema nuevo y reconstruir Export/web; los PDFs heredados requieren una migración revisada que conserva los archivos originales. [Actualizar Export](backend/DocumentExportServices/README.md#actualizar-una-instalación-existente). Si el mensaje todavía no está sincronizado, el PDF se crea sin asociarlo a ese mensaje; una conversación local tampoco se envía como referencia. Actualiza la web junto a Export para evitar referencias locales rechazadas. [Contrato de exportación](backend/DocumentExportServices/README.md#contrato-actual).

En el chat, **Mis PDFs** permite consultar el historial propio, cargar más, descargar o eliminar. Muestra 20 por página y los estados expirado/por revisar; el contador corresponde a PDFs cargados. Cancelar o cambiar de cuenta/tenant evita descargas tardías, y un reintento conserva la operación para no duplicar PDFs. Web, esquema y Export deben actualizarse juntos por el nuevo contrato paginado.

Las vistas de asignaciones, gestión y notificaciones cargan 50 registros por página. Usa **Cargar más** para consultar los siguientes. Los contadores de estas vistas indican registros cargados.

La biblioteca también carga por páginas de 50 las carpetas raíz, su contenido, favoritos y documentos actualizados recientemente. Usa **Cargar más** y **Actualizar biblioteca** para volver a las primeras páginas. Los contadores indican registros cargados; la cantidad de documentos de cada carpeta incluye todos los visibles. La web navega raíces y su contenido; la jerarquía completa está disponible en la API.

La ingesta admite archivos de hasta 20 MiB. Drive cuenta los bytes durante la descarga, con un máximo adicional de 100 MiB por lote, dos importaciones simultáneas y una por usuario. API, esquema y web deben actualizarse juntos por la nueva clave de operación. Si se pierde una respuesta, usa «Consultar importación pendiente»; las cargas inciertas requieren revisión y conservan su identificador de operación. [Contrato de importación y mantenimiento](backend/GoogleDriveImportServices/README.md#importaciones-acotadas-y-recuperables-drive-005).

## Servicios activos

- `backend/AuthServices`: autenticacion Django, usuarios y JWT.
- `backend/RagDocumentChatServices`: chat RAG sobre documentos.
- `backend/RagDocumentEmbeddingServices`: carga, extraccion, chunks y embeddings.
- `backend/DocumentSearchServices`: busqueda, detalle y seleccion documental.
- `backend/DocumentAccessServices`: preview, descarga, contenido y borrado.
- `backend/DocumentLibraryServices`: carpetas, favoritos y recientes.
- `backend/DocumentTransferServices`: historial de cargas/descargas.
- `backend/ConversationServices`: historial del chat documental. Usa **Cargar mensajes anteriores** para consultar páginas más antiguas.
- `backend/ProfileServices`: perfil y avatar.
- `backend/DocumentExportServices`: exportación PDF transaccional, historial paginado y rol mínimo. [Operación](backend/DocumentExportServices/README.md#ejecución-actual), [actualización](backend/DocumentExportServices/README.md#actualizar-una-instalación-existente) y [alcance del cierre](backend/DocumentExportServices/README.md#revisión-final-y-alcance).
- `backend/GoogleDriveImportServices`: integración opcional con Google Drive. [Contrato y operación](backend/GoogleDriveImportServices/README.md); OAuth PKCE, importación recuperable e historial propio paginado.
- `frontend`: interfaz React simple para chat y documentos.

## Arranque local con Docker

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Configura GROQ_API_KEY en .env.
docker compose -f docker/docker-compose.yml up -d --build --wait
```

En una instalación nueva, crea primero el administrador local como se indica abajo. Abre `http://localhost:3000`, inicia sesión y carga un documento de prueba. El primer uso de embeddings descarga el modelo. Por ejemplo, carga un archivo que diga «El plazo del contrato de prueba es de 97 días» y pregunta «¿Cuál es el plazo del contrato?».

La configuración de Compose y las credenciales de ejemplo están pensadas para una instancia de desarrollo local. Mantén tu clave de Groq en `.env` y usa datos sintéticos en la demo.

Compose provisiona el rol `conversation_runtime` al arrancar ConversationServices. Puedes cambiar su contraseña local con `CONVERSATION_DB_PASSWORD` en `.env`. [Operación de ConversationServices](backend/ConversationServices/README.md#running-the-service).

El chat RAG usa el rol `rag_chat_runtime`. Puedes cambiar su contraseña local con `RAG_CHAT_DB_PASSWORD` en `.env`. [Operación del chat RAG](backend/RagDocumentChatServices/README.md#running-the-service).

La ingesta usa el rol `embedding_runtime`. En Linux, crea `documents` como usuario local y configura `EMBEDDING_UID` y `EMBEDDING_GID` con los IDs de ese usuario antes de levantar Compose. [Operación de ingesta](backend/RagDocumentEmbeddingServices/README.md#running-the-service).

La búsqueda documental usa el rol de solo lectura `document_search_runtime`. Puedes cambiar su contraseña local con `SEARCH_DB_PASSWORD` en `.env`. [Operación de búsqueda](backend/DocumentSearchServices/README.md#running-the-service).

El acceso documental usa `document_access_runtime` y `ACCESS_DB_PASSWORD`. En Linux, configura `ACCESS_UID` y `ACCESS_GID` con el mismo propietario del directorio `documents` que usa la ingesta. [Permisos y operación de acceso](backend/DocumentAccessServices/README.md#running-the-service).

La biblioteca documental usa `document_library_runtime`, `LIBRARY_DB_PASSWORD` y una función acotada para bloquear referencias sin poder modificar documentos. Ejecuta sin root y mantiene configuración explícita y CORS local; `LIBRARY_CORS_ORIGINS` y `LIBRARY_DB_POOL_*` permiten ajustarlos. [Arranque y pruebas de Library](backend/DocumentLibraryServices/README.md#arranque-y-permisos).

El historial de transferencias usa document_transfer_runtime, TRANSFER_DB_PASSWORD, UID 10007 y una función de referencia acotada. Recibe solo configuración explícita y CORS local; usa `TRANSFER_CORS_ORIGINS` y `TRANSFER_DB_POOL_*` para ajustarlos. Su healthcheck comprueba PostgreSQL y la clave pública. El historial carga páginas de 50 con Cargar más y Actualizar historial; el contador indica registros cargados. Cada limpieza retira hasta 1000 procesos terminados propios y conserva los activos; repite la acción si quedan registros. Un fallo del historial muestra un aviso y no repite ni bloquea la operación documental. [Operación y pruebas de Transfer](backend/DocumentTransferServices/README.md#operación).

Profile recibe solo configuración explícita y CORS local. Valida PostgreSQL y clave pública al arrancar y en `/api/v1/health/db`; usa `PROFILE_CORS_ORIGINS`, `PROFILE_DB_POOL_*` y `PROFILE_DB_TIMEOUT_SECONDS` para ajustar operación. Los datos del perfil solo se consultan/editan con la sesión vigente del dueño, sin acceso administrativo global; las antiguas rutas `/api/v1/profiles` y por ID se retiraron. Los avatares son privados, normalizados a JPEG y guardados en PostgreSQL con control de versión. Se retiró `/static`; la web los descarga con JWT. Usa el rol `profile_runtime` y `PROFILE_DB_PASSWORD`, con comprobación booleana de identidad sin leer contraseñas directamente. Los avisos residuales de imagen se registran en PROFILE-F01/F02. [Contrato, operación y pruebas de Profile](backend/ProfileServices/README.md#contrato-actual).

Si otra instalación de PostgreSQL ocupa el puerto local 5432, configura `POSTGRES_HOST_PORT=15432` en `.env`. Los contenedores siguen conectándose a PostgreSQL por el puerto interno 5432.

El agregador `docker/docker-compose.yml` carga:

- `compose/infra.yml`
- `compose/auth.yml`
- `compose/documents.yml`
- `compose/collaboration.yml`
- `compose/profile.yml`
- `compose/export.yml`
- `compose/frontend.yml`

URLs principales:

- Frontend: `http://localhost:3000`
- Auth: `http://localhost:8001`
- Chat RAG: `http://localhost:8002`
- Ingestion/embeddings: `http://localhost:8003`
- Busqueda documental: `http://localhost:8004`
- Acceso documental: `http://localhost:8005`
- Biblioteca: `http://localhost:8006`
- Transferencias: `http://localhost:8007`
- Conversaciones: `http://localhost:8008`
- Perfil: `http://localhost:8015`
- Exportaciones: `http://localhost:8016`
- Google Drive import: `http://localhost:8017`

## Ejecucion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/RagDocumentChatServices/requirements.txt
pip install -r backend/RagDocumentEmbeddingServices/requirements.txt
pip install -r backend/DocumentSearchServices/requirements.txt
pip install -r backend/DocumentAccessServices/requirements.txt
copy .env.example .env
```

Servicios documentales principales:

```bash
make run-chat
make run-embedding
make run-search
make run-access
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Base de datos

El esquema SQL vive en `scripts/database/run_all.sql` y ahora carga solo dominios documentales:

- documentos y embeddings
- conversaciones
- perfiles
- exportaciones
- importaciones de Google Drive
- constraints, indices, funciones, triggers y seeds necesarios

## Credenciales locales

La creación del administrador es explícita. Desde la raíz y con el stack activo, ejecuta el comando y elige tu contraseña en el prompt:

```powershell
docker compose -f docker/docker-compose.yml exec auth-service python manage.py createsuperuser
```

Para actualizar desde la versión con un volumen JWT compartido, sigue el [procedimiento de AuthServices](backend/AuthServices/docs/OPERATIONS.md#actualización-desde-el-volumen-jwt-compartido).

## Scripts utiles

Procesar documentos pendientes:

```bash
python scripts/process_pending_documents.py --limit 10
```

Reindexar documentos:

```bash
python scripts/reindex_documents.py --all --limit 100
```

### Embeddings locales

La ingesta y el chat usan `intfloat/multilingual-e5-small` en CPU. El primer uso descarga el modelo. Las instalaciones nuevas crean el índice con vectores de 384 dimensiones.

Para actualizar una instalación existente, detén la ingesta y el chat, respalda la base y ejecuta `scripts/database/migrations/001_local_embeddings.sql` con `psql` conectado a la base documental. La migración elimina los vectores de 1536 dimensiones y marca sus documentos para reindexar. Los archivos originales se conservan. Con el almacenamiento documental disponible, ejecuta el script de reindexación por lotes antes de volver a habilitar el chat.

### Prueba del recorrido documental

La actualización del esquema incluye la auditoría de integridad de carpetas. Si detecta relaciones, ciclos o nombres inválidos, aborta sin borrar datos. Consulta la [operación de Library](backend/DocumentLibraryServices/README.md#integridad-y-migración-de-carpetas) antes de actualizar una base existente.

Con el stack local activo y `GROQ_API_KEY` configurada, ejecuta desde PowerShell 7:

```powershell
./scripts/smoke_documental.ps1 -Credential (Get-Credential)
```

La prueba inicia sesión, carga e indexa un documento sintético, lo reindexa, comprueba su recuperación y descarga un PDF con la respuesta. Usa una instancia de desarrollo, ya que el documento y la exportación quedan registrados. Para verificar aislamiento, pasa también `-ObserverCredential` con un segundo usuario que tenga permiso `use_chat` y carezca de acceso al documento.
