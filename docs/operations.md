# Operación local

La instalación soportada usa Docker Compose y publica web, APIs y PostgreSQL en loopback. Ejecuta los comandos desde la raíz y usa `--env-file .env` para que los archivos incluidos por Compose reciban la configuración. La [verificación de entrega](release/README.md) usa un proyecto y credenciales sintéticas independientes.

## Configuración y diagnóstico

| Variable o función | Operación |
| --- | --- |
| `POSTGRES_PASSWORD` | Configura la contraseña del operador PostgreSQL. Con un volumen existente conserva el valor vigente y usa el procedimiento de rotación si necesitas cambiarlo. |
| `DJANGO_SECRET_KEY` | Genera un secreto aleatorio propio para Auth. |
| `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL` | Define el administrador inicial con una contraseña válida para Django. El correo es opcional. Si ya existe un superusuario, se conservan su contraseña, estado y privilegios. Si el nombre corresponde a una cuenta normal y todavía falta un superusuario, el bootstrap falla. Retira las variables iniciales tras completar el alta. |
| `GROQ_API_KEY` | Configura una clave de desarrollo para probar el chat con Groq (fallback de entorno). También puede gestionarse por empresa desde **Configuración IA** (`/settings/ai`) sin reiniciar contenedores. Usa documentos sintéticos porque la pregunta y el contexto recuperado se envían al proveedor. |
| `SECRETS_ENCRYPTION_KEY`, `SECRETS_KEY_ID`, `SECRETS_PREVIOUS_KEYS` | Llavero Fernet (`secrets1.`) para cifrar en reposo credenciales de IA guardadas desde `/settings/ai` en `tenant_integrations`. Requiere una clave maestra aleatoria de al menos 32 caracteres (sin prefijos de ejemplo). |
| `POSTGRES_HOST_PORT` | Si el puerto local 5432 está ocupado, usa por ejemplo `15432`. Los servicios mantienen 5432 dentro de Compose. |
| `EMBEDDING_UID`, `EMBEDDING_GID`, `ACCESS_UID`, `ACCESS_GID` | En un directorio documental existente, configura el UID/GID para que ambos servicios puedan acceder con los permisos actuales. El inicializador asigna propietario en un directorio nuevo vacío y conserva los archivos y permisos existentes. |
| `GOOGLE_DRIVE_ENABLED`, `DRIVE_DB_PASSWORD` | Drive arranca deshabilitado. Conserva disponibilidad e historial autorizado y devuelve 503 en operaciones con el proveedor. Para habilitar OAuth, consulta el contrato de Drive y aprovisiona su rol de base de datos. |
| `STUDIO_ENABLED`, `STUDIO_DB_PASSWORD` | Knowledge Studio es opcional y arranca deshabilitado (`STUDIO_ENABLED=false`). Levántalo con el overlay `docker/compose/studio.yml` (`--profile studio`) y su rol mínimo `studio_runtime`. En la web se accede en `/studio`, la auditoría administrativa en `/admin/audit` y la configuración de IA en `/settings/ai`. |
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

Para desarrollar sin Compose, consulta el README del servicio y configura el rol de base de datos y, cuando corresponda, `AUTH_JWT_PUBLIC_KEY_PATH` y `AUTH_IDENTITY_URL` con Auth activo. Para desarrollar solo la interfaz, ejecuta `npm ci` y `npm run dev` desde `frontend/`. En Linux/macOS (o WSL/Git Bash), el [Makefile](../Makefile) de la raíz agrupa atajos equivalentes para los once servicios (`make help`, `make up`, `make compose-config`, `make run-<servicio>`, `make check-docs`, `make test-services` y `make verify`). [Mapa de servicios](architecture.md#mapa-de-servicios) · [Frontend](../frontend/README.md)
