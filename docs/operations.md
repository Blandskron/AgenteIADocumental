# Operación local

La instalación soportada usa Docker Compose y publica web, APIs y PostgreSQL en loopback. Ejecuta los comandos desde la raíz y usa `--env-file .env` para que los archivos incluidos por Compose reciban la configuración. La [verificación de entrega](release/README.md) usa un proyecto y credenciales sintéticas independientes.

## Configuración y diagnóstico

| Variable o función | Operación |
| --- | --- |
| `POSTGRES_PASSWORD` | Configura la contraseña del operador PostgreSQL. Con un volumen existente conserva el valor vigente y usa el procedimiento de rotación si necesitas cambiarlo. |
| `DJANGO_SECRET_KEY` | Genera un secreto aleatorio propio para Auth. |
| `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL` | Define el administrador inicial con una contraseña válida para Django. El correo es opcional. Si ya existe un superusuario, se conservan su contraseña, estado y privilegios. Si el nombre corresponde a una cuenta normal y todavía falta un superusuario, el bootstrap falla. Retira las variables iniciales tras completar el alta. |
| `GROQ_API_KEY` | Configura una clave de desarrollo para probar el chat con Groq. Usa documentos sintéticos porque la pregunta y el contexto recuperado se envían al proveedor. |
| `POSTGRES_HOST_PORT` | Si el puerto local 5432 está ocupado, usa por ejemplo `15432`. Los servicios mantienen 5432 dentro de Compose. |
| `EMBEDDING_UID`, `EMBEDDING_GID`, `ACCESS_UID`, `ACCESS_GID` | En un directorio documental existente, configura el UID/GID para que ambos servicios puedan acceder con los permisos actuales. El inicializador asigna propietario en un directorio nuevo vacío y conserva los archivos y permisos existentes. |
| `GOOGLE_DRIVE_ENABLED`, `DRIVE_DB_PASSWORD` | Drive arranca deshabilitado. Conserva disponibilidad e historial autorizado y devuelve 503 en operaciones con el proveedor. Para habilitar OAuth, consulta el contrato de Drive y aprovisiona su rol de base de datos. |
| pgAdmin | Perfil `tools`. Configura `PGADMIN_DEFAULT_EMAIL` y `PGADMIN_DEFAULT_PASSWORD` antes de activarlo. |

Consulta la plantilla de entorno y los contratos para las contraseñas por rol, CORS, pools y montajes. [Plantilla de entorno](../.env.example) · [Mapa de servicios](architecture.md#mapa-de-servicios) · [OAuth de Google Drive](../backend/GoogleDriveImportServices/README.md)

```powershell
docker compose --env-file .env -f docker/docker-compose.yml config --quiet
docker compose --env-file .env -f docker/docker-compose.yml ps -a
docker compose --env-file .env -f docker/docker-compose.yml logs --tail 100 auth-service tenant-integrity
```

Si el arranque falla, identifica primero el job que terminó con error. El orden principal de identidad es PostgreSQL saludable → esquema compartido → roles Auth → migraciones Django → integridad de membresías → bootstrap → Auth. Los jobs de rol y preparación de almacenamiento habilitan a sus consumidores. [Agregador de Compose](../docker/docker-compose.yml) · [Arranque de Auth](../docker/compose/auth.yml)

Para iniciar pgAdmin de forma opcional:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml --profile tools up -d pgadmin
```

## Actualizar una instalación existente

1. Detén los escritores y crea una copia coherente de PostgreSQL, originales y claves JWT.
2. Ejecuta el preflight de solo lectura y revisa el diagnóstico de relaciones multiempresa. Resuelve cualquier inconsistencia mediante el procedimiento del esquema antes de actualizar. Los jobs de integridad detienen el arranque ante referencias o jerarquías inválidas.
3. Revisa las migraciones aplicables. La migración de embeddings de 1536 a 384 dimensiones retira los vectores heredados y conserva los originales. Reindexa antes de habilitar chat. Para el antiguo volumen JWT compartido, sigue la guía de Auth. Para PDFs heredados, sigue la migración revisada de Exportación.
4. Actualiza esquema, API y web de forma coordinada. Revisa los healthchecks y prueba con datos sintéticos.

[Esquema y preflight](../scripts/database/README.md) · [Integridad de carpetas](../backend/DocumentLibraryServices/README.md#integridad-y-migración-de-carpetas) · [Claves JWT](../backend/AuthServices/docs/OPERATIONS.md#actualización-desde-el-volumen-jwt-compartido) · [Migración de PDF](../backend/DocumentExportServices/README.md#migración-revisada-de-pdfs-heredados)

## Procesamiento y prueba funcional

Los scripts de procesamiento directo requieren el entorno Python del servicio de ingesta, la conexión de base de datos y acceso al almacenamiento documental. Consulta el [contrato de ingesta](../backend/RagDocumentEmbeddingServices/README.md) antes de ejecutarlos.

```powershell
python scripts/process_pending_documents.py --limit 10
python scripts/reindex_documents.py --all --limit 100
```

Con el stack de desarrollo activo y una clave de Groq, la prueba de PowerShell 7 carga, indexa, reindexa y recupera un documento sintético, y descarga un PDF. La prueba deja el documento y la exportación registrados. Para comprobar aislamiento, añade `-ObserverCredential (Get-Credential)` con un segundo usuario que tenga permiso `use_chat` y carezca de acceso al documento.

```powershell
./scripts/smoke_documental.ps1 -Credential (Get-Credential)
```

Para desarrollar sin Compose, consulta el README del servicio y configura el rol de base de datos y, cuando corresponda, `AUTH_JWT_PUBLIC_KEY_PATH` y `AUTH_IDENTITY_URL` con Auth activo. Para desarrollar solo la interfaz, ejecuta `npm ci` y `npm run dev` desde `frontend/`. [Mapa de servicios](architecture.md#mapa-de-servicios) · [Frontend](../frontend/README.md)
