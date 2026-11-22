# Operación local

La instalación soportada usa Docker Compose desde la raíz (`docker compose up -d --build`) y publica web, APIs y PostgreSQL en loopback (`127.0.0.1`). No necesitas crear `.env` manualmente para arrancar: `secrets-init` genera secretos aleatorios fuertes en el volumen persistente `runtime_secrets` y respeta cualquier `.env` ya existente. La [verificación de entrega](release/README.md) usa un proyecto y credenciales sintéticas independientes.

## Configuración y diagnóstico

| Variable o función | Operación |
| --- | --- |
| `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `SECRETS_ENCRYPTION_KEY` | Opcionales en desarrollo local (generadas automáticamente en `runtime_secrets` si faltan). En instalaciones existentes con `.env`, se conservan y aplican sus valores vigentes. |
| `ALLOW_WEB_SETUP`, `INITIAL_ADMIN_*` | Con `ALLOW_WEB_SETUP=true` (por defecto en Compose), si no defines `INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD`, puedes crear la primera cuenta administradora desde `http://localhost:3000`. |
| `GOOGLE_OIDC_CLIENT_ID`, `EMAIL_HOST` | Opcionales y deshabilitadas por defecto. `GOOGLE_OIDC_CLIENT_ID` habilita Google Login (OIDC); `EMAIL_HOST` habilita recuperación de contraseña por correo. |
| `GROQ_API_KEY`, `OLLAMA_BASE_URL` | Puedes elegir **Groq** u **Ollama local** desde `/settings/ai` sin reiniciar servicios. `GROQ_API_KEY` actúa como fallback de entorno; `OLLAMA_BASE_URL` apunta por defecto a `http://ollama:11434` con el perfil `--profile local-llm`. |
| `POSTGRES_HOST_PORT` | Si el puerto local 5432 está ocupado, usa por ejemplo `15432`. Los servicios mantienen 5432 dentro de Compose. |
| `EMBEDDING_UID`, `EMBEDDING_GID`, `ACCESS_UID`, `ACCESS_GID` | En un directorio documental existente, configura el UID/GID para que ambos servicios puedan acceder con los permisos actuales. El inicializador asigna propietario en un directorio nuevo vacío y conserva los archivos y permisos existentes. |
| `GOOGLE_DRIVE_ENABLED`, `DRIVE_DB_PASSWORD` | Drive arranca deshabilitado. Conserva disponibilidad e historial autorizado y devuelve 503 en operaciones con el proveedor. Para habilitar OAuth, consulta el contrato de Drive y aprovisiona su rol de base de datos. |
| `STUDIO_ENABLED`, `STUDIO_DB_PASSWORD` | Knowledge Studio es opcional y arranca deshabilitado (`STUDIO_ENABLED=false`). Levántalo con el overlay `docker/compose/studio.yml` (`--profile studio`) y su rol mínimo `studio_runtime`. En la web se accede en `/studio`, la auditoría administrativa en `/admin/audit` y la configuración de IA en `/settings/ai`. |
| `AGENTS_ENABLED`, `CODE_MODE_ENABLED`, `AGENT_DB_PASSWORD` | Orquestación agéntica (`--profile agents`, puerto `8019`, esquema `agents.*`) y sandbox Code Mode (`--profile code-mode`, red interna `code_sandbox_net` sin salida a internet). Deshabilitados por defecto sin impacto en el stack base. Consulta [ADR-006](ADR_AGENT_ORCHESTRATOR.md) y [ADR-007](ADR_CODE_MODE_SANDBOX.md). |
| `OLLAMA_HOST_PORT` | Overlay opcional `docker/compose/ollama.yml` (`--profile local-llm`) para proveedores OpenAI-compatible locales en loopback. |
| `POSTGRES_DATA_VOLUME` | Selecciona el volumen PostgreSQL tras una restauración. El valor predeterminado conserva el nombre asociado al proyecto de Compose. |

Consulta la plantilla de entorno y los contratos para las contraseñas por rol, CORS, pools y montajes. [Plantilla de entorno](../.env.example) · [Mapa de servicios](architecture.md#mapa-de-servicios) · [OAuth de Google Drive](../backend/GoogleDriveImportServices/README.md)

```powershell
docker compose --env-file .env -f docker/docker-compose.yml config --quiet
docker compose --env-file .env -f docker/docker-compose.yml ps -a
docker compose --env-file .env -f docker/docker-compose.yml logs --tail 100 auth-service tenant-integrity
```

Si el arranque falla, identifica primero el job que terminó con error. El orden principal de identidad es PostgreSQL saludable → esquema compartido → roles Auth → migraciones Django → integridad de membresías → bootstrap → Auth. Los jobs de rol y preparación de almacenamiento habilitan a sus consumidores. [Agregador de Compose](../docker/docker-compose.yml) · [Arranque de Auth](../docker/compose/auth.yml)

Para abrir una sesión SQL local con la herramienta incluida en la imagen:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec postgres psql -U postgres -d documents_db
```

## Actualizar una instalación existente

1. Detén los escritores y crea una copia coherente de PostgreSQL, originales y claves JWT.
2. Ejecuta el preflight de solo lectura y revisa el diagnóstico de relaciones multiempresa. Resuelve cualquier inconsistencia mediante el procedimiento del esquema antes de actualizar. Los jobs de integridad detienen el arranque ante referencias o jerarquías inválidas.
3. Revisa las migraciones aplicables. La migración de embeddings de 1536 a 384 dimensiones retira los vectores heredados y conserva los originales. Reindexa antes de habilitar chat. Para el antiguo volumen JWT compartido, sigue la guía de Auth. Para PDFs heredados, sigue la migración revisada de Exportación.
4. Actualiza esquema, API y web de forma coordinada. Revisa los healthchecks y prueba con datos sintéticos.

[Esquema y preflight](../scripts/database/README.md) · [Integridad de carpetas](../backend/DocumentLibraryServices/docs/REFERENCE.md#integridad-y-migración-de-carpetas) · [Claves JWT](../backend/AuthServices/docs/OPERATIONS.md#actualización-desde-el-volumen-jwt-compartido) · [Migración de PDF](../backend/DocumentExportServices/docs/REFERENCE.md#migración-revisada-de-pdfs-heredados)

## Migrar la imagen de PostgreSQL

El cambio de Debian a Alpine conserva PostgreSQL 16 y reconstruye los índices con la colación ICU del destino. La imagen detecta el directorio de datos anterior y detiene el arranque. Para migrar, detén los escritores y guarda una copia privada de los originales y de los volúmenes de claves JWT. Conserva la clave de cifrado de Drive si usas esa integración. El procedimiento siguiente copia los roles del clúster y la base `documents_db`. Si agregaste otras bases o tablespaces, incluye sus respaldos y verifica cómo restaurarlos antes de continuar.

Desde PowerShell, en la raíz, usa el contenedor antiguo existente. Si ya fue reemplazado, vuelve a la revisión anterior y levanta únicamente su servicio PostgreSQL sobre el volumen original antes de respaldar.

```powershell
$compose = @('--env-file', '.env', '-f', 'docker/docker-compose.yml')
docker compose @compose stop
docker start rag-documents-postgres
$backup = New-Item -ItemType Directory -Path (Join-Path $env:LOCALAPPDATA ("documental-backup-" + [Guid]::NewGuid()))
docker exec rag-documents-postgres mkdir -m 700 /tmp/documental-backup
docker exec rag-documents-postgres pg_dumpall -U postgres --roles-only -f /tmp/documental-backup/roles.sql
docker exec rag-documents-postgres pg_dump -U postgres -Fc -f /tmp/documental-backup/documents.dump documents_db
docker cp rag-documents-postgres:/tmp/documental-backup/. $backup.FullName
docker stop rag-documents-postgres
```

Comprueba que ambos archivos se copiaron y conserva la carpeta privada. El archivo de roles contiene verificadores de contraseñas. Define en `.env` un `POSTGRES_DATA_VOLUME` nuevo y vacío. Mantén las credenciales PostgreSQL y de los roles coordinadas con las que usaba la instalación anterior. El perfil de restauración arranca PostgreSQL de forma aislada y deja que el respaldo cree el esquema y los índices.

```powershell
$restore = $compose + @('-f', 'docker/compose/restore.yml')
docker compose @restore up -d --build --wait postgres
docker compose @restore cp $backup.FullName postgres:/tmp/documental-backup
docker compose @restore cp scripts/database/tools/restore_postgres16.sh postgres:/tmp/restore-postgres16.sh
docker compose @restore exec -T postgres sh /tmp/restore-postgres16.sh /tmp/documental-backup
```

Si la restauración devuelve un error, detén el procedimiento y conserva ambos volúmenes. Cuando termine correctamente, vuelve a la configuración normal y valida inicio de sesión, documentos existentes e índices. Mantén el volumen anterior hasta completar las pruebas. Para volver a la revisión anterior, detén el stack y vuelve a indicar el volumen original, junto con su copia coherente de originales y claves cuando corresponda.

```powershell
docker compose @compose up -d --build --wait
```

## Procesamiento y prueba funcional

Los scripts de procesamiento directo requieren el entorno Python del servicio de ingesta, la conexión de base de datos y acceso al almacenamiento documental. En una ejecución fuera de Docker, prepara la revisión del modelo en `E5_MODEL_DIR` antes de procesar documentos. [Contrato de ingesta](../backend/RagDocumentEmbeddingServices/README.md)

```powershell
$env:E5_MODEL_DIR = Join-Path $env:LOCALAPPDATA 'blandskron-models/multilingual-e5-small'
$modelFiles = @('1_Pooling/config.json', 'config.json', 'modules.json', 'sentence_bert_config.json',
    'special_tokens_map.json', 'tokenizer_config.json', 'tokenizer.json', 'sentencepiece.bpe.model', 'model.safetensors')
hf download intfloat/multilingual-e5-small @modelFiles --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --local-dir $env:E5_MODEL_DIR
python scripts/process_pending_documents.py --limit 10
python scripts/reindex_documents.py --all --limit 100
```

Con el stack de desarrollo activo y una clave de Groq, la prueba de PowerShell 7 carga, indexa, reindexa y recupera un documento sintético, y descarga un PDF. La prueba deja el documento y la exportación registrados. Para comprobar aislamiento, añade `-ObserverCredential (Get-Credential)` con un segundo usuario que tenga permiso `use_chat` y carezca de acceso al documento.

```powershell
./scripts/smoke_documental.ps1 -Credential (Get-Credential)
```

Para desarrollar sin Compose, consulta el README del servicio y configura el rol de base de datos y, cuando corresponda, `AUTH_JWT_PUBLIC_KEY_PATH` y `AUTH_IDENTITY_URL` con Auth activo. Para desarrollar solo la interfaz, ejecuta `npm ci` y `npm run dev` desde `frontend/`. En Linux/macOS (o WSL/Git Bash), el [Makefile](../Makefile) de la raíz agrupa atajos equivalentes para los once servicios (`make help`, `make up`, `make compose-config`, `make run-<servicio>`, `make check-docs`, `make test-services`, `make eval-rag-matrix` y `make verify`). [Mapa de servicios](architecture.md#mapa-de-servicios) · [Frontend](../frontend/README.md)

## Resiliencia, solución de problemas y desinstalación segura

- **Caída temporal de PostgreSQL:** los servicios FastAPI exponen `/api/v1/health/db` y reconectan mediante `pool_pre_ping`; si un contenedor queda `unhealthy`, revisa `docker compose logs postgres` y reinicia con `docker compose up -d`.
- **Caída de Groq o cuota agotada:** el chat devuelve un estado tipificado (`rate_limited`, `auth_error`, `provider_error`) sin bloquear la búsqueda ni la biblioteca. Puedes cambiar a **Ollama local** en `/settings/ai` sin reiniciar servicios.
- **Ollama no accesible o memoria insuficiente:** verifica que levantaste el perfil `--profile local-llm` (`docker compose -f compose.yaml -f docker/compose/ollama.yml --profile local-llm ps`). Si un modelo de 7B excede la RAM disponible, selecciona un modelo más ligero del catálogo autorizado (`gemma2:2b` o `qwen2.5:3b`).
- **Desinstalación sin pérdida accidental de datos:**
  - `docker compose down` detiene y elimina contenedores conservando los volúmenes `postgres_data`, `runtime_secrets`, `auth_signing_keys`, `auth_verification_keys`, `ollama_models` y la carpeta `./documents`.
  - Solo usa `docker compose down -v` si deseas borrar permanentemente la base de datos y los secretos locales.
- **Medición de latencias en ejecución real:** con el stack activo, ejecuta `python3 scripts/eval/benchmark_local_budget.py` para registrar mediciones reales en `.release-reports/PERFORMANCE_BUDGET.json`.
