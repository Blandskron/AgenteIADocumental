# ProfileServices

> Evidencia transversal vigente: [verificación de entrega](../../docs/release/README.md) e [imágenes finales](../../docs/release/IMAGE_AUDIT.json). Runtime Python sin pip/ensurepip; comprobación del grafo durante el build, herramientas en test/audit. Los escaneos fechados anteriores conservan su valor histórico y no describen esta imagen.

Servicio FastAPI de perfil y avatar de Blandskron Documental, publicado localmente en `http://localhost:8015`. AuthServices administra identidad, credenciales y membresías; Profile guarda contacto, presentación y avatar privado en `user_profiles` (PostgreSQL).

**Estado:** cierre funcional PROFILE-008 integrado mediante PR #66, con seis checks aprobados. Perfil propio versionado, avatar privado en PostgreSQL, cliente web aislado por sesión y rol mínimo con revocación de Auth. Persisten los seguimientos explícitos de imagen PROFILE-F01/F02, integridad compartida PLAT-001 y frontend WEB-001; el proyecto completo todavía no está terminado. El [tablero](../../ROADMAP.md#profileservices) registra la integración y el trabajo siguiente.

## Mapa para trabajar

| Ubicación | Responsabilidad actual |
| --- | --- |
| `app/main.py` | Factory `create_app`, lifespan, CORS y excepciones |
| `app/config/` | Settings, JWT, logging y sesión por petición |
| `app/interfaces/api/v1/` | Salud, perfil propio, upload/lectura/borrado de avatar y límites HTTP |
| `app/application/use_cases/manage_profile.py` | Perfil propio vacío cuando no existe y actualización |
| `app/domain/entities.py` | Entidad de perfil |
| `app/infrastructure/database/` | SQLAlchemy, sesiones y repositorio PostgreSQL |
| [Esquema](../../scripts/database/schemas/008_profiles.sql) y [triggers](../../scripts/database/triggers/001_updated_at_triggers.sql) | PK generada, `user_id` único, metadata JSONB y `updated_at` |
| [Versiones](../../scripts/database/profile/versions.sql) y [preflight](../../scripts/database/profile/audit_profiles.sql) | Migración aditiva/repetible y conteos de datos heredados sin exponer valores |
| [Compose](../../docker/compose/profile.yml) | Puerto, clave pública de Auth, runtime sin root y mantenimiento optativo |
| [Cliente web](../../frontend/src/features/profile/api/profile.api.js), [hook](../../frontend/src/features/profile/hooks/useProfile.js) y [página](../../frontend/src/pages/ProfilePage/ProfilePage.jsx) | Consulta/actualización propia, upload y cambio de contraseña vía Auth |
| [AuthProvider](../../frontend/src/app/providers/AuthProvider.jsx) y [Sidebar](../../frontend/src/widgets/Sidebar/Sidebar.jsx) | Perfil global y avatar |

`tests/` contiene la suite permanente y CI la ejecuta sobre PostgreSQL. Las etapas Docker `runtime`, `test` y `audit` separan las herramientas del servicio; el inventario auditado se captura antes de instalar pip-audit.

## Contrato actual

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| GET | `/api/v1/health` | Público; devuelve `status: ok`, sin comprobar dependencias |
| GET | `/api/v1/health/db` | Público; comprueba esquema de perfil/identidad y clave pública; 503 genérico si fallan |
| GET | `/api/v1/profile` | Perfil propio y versión; entidad vacía con versión 0 si no existe; consultar no inserta |
| PUT | `/api/v1/profile` | Creación/actualización parcial condicionada por `expected_version` |
| POST | `/api/v1/profile/upload` | Multipart `file` + `expected_version`; normaliza y asocia avatar; devuelve ProfileResponse y nueva versión |
| GET | `/api/v1/profile/avatar?version=N` | JPEG propio; 404 si falta o cambió la versión. Sin parámetro devuelve el vigente |
| DELETE | `/api/v1/profile/avatar` | JSON `expected_version`; retira los bytes propios e incrementa versión; devuelve ProfileResponse |

Las operaciones de perfil y avatar requieren Bearer access RS256 y cuenta vigente. `user_id` debe ser un entero positivo dentro de int64 (no booleano, cadena ni decimal). Se exigen `exp`, `iat`, `jti`, `token_type` y `hash_password`; tiempos enteros válidos, `iat` no negativo y anterior a `exp`, `jti` no vacío de hasta 128 caracteres y tipo `access`. Un `sub` opcional debe ser la cadena decimal canónica del mismo ID; no hay fallback a `username`. Flags booleanos y listas de grupos/permisos/roles, si aparecen, deben tener tipos correctos. El contrato actual de Auth no emite issuer/audience; no se introducen valores inventados que rompan login.

Cada petición autenticada consulta si `public.auth_user` contiene ese ID activo y si `upper(md5(password))` coincide con `hash_password`, como `CHECK_REVOKE_TOKEN` de SimpleJWT en Auth. La expresión opera sobre la contraseña **ya codificada por Django** y reproduce su huella de revocación; no reemplaza el algoritmo de contraseña por MD5. La consulta devuelve solo un booleano, nunca la contraseña codificada. Una cuenta inexistente/inactiva/eliminada o contraseña cambiada devuelve 401 genérico con `WWW-Authenticate: Bearer`; un fallo de consulta devuelve 503 sin detalles internos.

El repositorio queda ligado al dueño autenticado al construirse: consultas y escrituras no reciben un ID de destino del cliente ni disponen de listado global. Ser superadmin, staff o administrador de tenant no amplía ese alcance. La consulta de vigencia usa `FOR SHARE` sobre la fila de Auth hasta el commit/cierre de sesión: un cambio de contraseña, desactivación o eliminación concurrente espera la operación ya autorizada. Si ese cambio estaba en curso primero, la comprobación espera y reevalúa el estado antes de autorizar. Los timeouts cierran el acceso con 503. Las relaciones históricas y restricciones compartidas permanecen en PLAT-001; la función booleana y los permisos mínimos de este lock se entregan en PROFILE-007.

**Transición de contrato:** se retiran `GET /api/v1/profiles`, `GET /api/v1/profiles/{user_id}` y `PUT /api/v1/profiles/{user_id}`. Devuelven 404 y no figuran en OpenAPI, incluso para el propio ID o administradores. La búsqueda de consumidores no encontró usos en la web; las integraciones externas deben usar `/api/v1/profile` con la sesión del dueño. Los tokens anteriores sin los claims requeridos se rechazan; renueva la sesión en Auth. No se reasignan ni eliminan automáticamente perfiles heredados: registros asociados a username o IDs no canónicos requieren inventario y reparación explícita según el preflight, sin reasignarlos automáticamente.

### Escrituras, límites y conflictos

PUT mantiene la actualización parcial, con `expected_version` obligatorio y al menos un campo editable. GET devuelve `version: 0` cuando aún no hay fila y una versión positiva en registros persistidos. Las respuestas funcionales usan Cache-Control: no-store para evitar versiones personales cacheadas. Envía esa versión en el siguiente guardado; la respuesta aprobada devuelve la nueva. La creación usa INSERT con conflicto controlado sobre `user_id`; una actualización modifica solo la fila del dueño con la versión esperada, incrementándola. Dos peticiones con la misma versión producen un éxito y un 409; no se reintenta una sobrescritura automáticamente.

| Campo | Validación de entrada |
| --- | --- |
| `expected_version` | Entero estricto entre 0 y 2⁶³−2; 0 solo crea si la fila no existe |
| `email` | Email de contacto, hasta 254 caracteres, validado/normalizado por email-validator sin consultas de entregabilidad |
| `phone_number` | Hasta 32 caracteres; dígitos y separadores `+ ()-.x#`, al menos tres dígitos; no certifica país o existencia del número |
| `profile_picture_url` | Solo `null` explícito para retirar la foto; omitir conserva. No acepta URL externa, ruta ni cadena vacía |
| `additional_info` | Objeto JSON de hasta 16 KiB serializado UTF-8, profundidad 4 desde su raíz, 256 nodos totales, 64 claves por objeto y claves de 1–64 caracteres sin controles. Strings hasta 2048, sin NUL ni codificación inválida; números finitos |

Los campos de presentación dentro de metadata deben ser cadenas: `full_name`, `location`, `position` y `department` hasta 120 caracteres; `bio` hasta 2000 y `preferred_language` hasta 16. Otros campos JSON pueden conservarse dentro de los límites. No se aceptan campos superiores desconocidos, incluyendo `user_id`, `version`, roles o permisos. El JSON completo de PUT está limitado a 65536 bytes reales, incluso sin Content-Length o por chunks; hasta 16 niveles y 2048 nodos antes de validar el esquema. Multipart tiene un límite independiente de 5 MiB + 64 KiB de sobre HTTP.

Omitir un campo conserva su valor. `null` borra email/teléfono/avatar; `""` o espacios se normalizan a null solo en email/teléfono. `additional_info: null` o `{}` vacían metadata, y un objeto enviado la reemplaza completa. Por ejemplo, tras leer versión 3:

```json
{"expected_version":3,"phone_number":null,"additional_info":{"full_name":"Persona sintética"}}
```

Un éxito devuelve versión 4 y conserva email/URL omitidos. La web envía la versión leída, conserva el formulario ante conflicto y permite **Descartar cambios y recargar perfil** mediante acción explícita. El cliente HTTP no reintenta un 409. PROFILE-006 conserva edición durante renovación de JWT y upload, e invalida estados al cambiar sesión.

Respuestas de error: 400 para JSON inválido o estructura general excesiva, 413 para cuerpo mayor al límite, 422 para campos/esquema inválidos, 409 para versión obsoleta o conflicto de integridad y 503 para persistencia no disponible. Las respuestas no reflejan valores, nombres de campos desconocidos, consultas, parámetros SQL ni contexto de validación. Los timeouts y fallos revierten la transacción; el trigger existente conserva `updated_at`, y la versión evita depender de su precisión como condición de concurrencia.

La respuesta contiene `profile_id`, `user_id`, `version`, los cuatro campos editables y `created_at`/`updated_at`. Añade `groups` y `permissions` del JWT validado para mostrar el contexto de la sesión; no son una nueva fuente de autorización ni se refrescan desde membresías en Profile. Cambios de permisos se reflejan al renovar el token en Auth. No se devuelven huella, contraseña, jti ni otros internos del token. Este email no actualiza `auth_user.email`, las credenciales ni los claims de Auth.

La revocación aquí cubre cambio de contraseña y estado/existencia de cuenta. El logout de Auth invalida el refresh; un access ya emitido puede seguir válido hasta su expiración (10 minutos según Auth), salvo cambio de contraseña o cuenta. No se afirma revocación instantánea de access por logout.

El upload exige la misma identidad vigente y versión que el perfil, normaliza el contenido a JPEG y lo asocia directamente en PostgreSQL. No reutiliza nombres enviados ni conserva los bytes originales. `/static` está retirado. El ciclo privado y el mantenimiento revisado se detallan abajo.

## Arranque y configuración actuales

Desde la raíz, con `.env` local ya configurado:

```powershell
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait profile-service
```

El runtime no monta `uploads/profile`; los avatares privados residen en PostgreSQL. Solo la herramienta optativa de mantenimiento monta las fuentes antiguas en lectura. Las pruebas usan directorios sintéticos temporales y rollback; el directorio real de uploads no se necesita para el runtime. No se necesita clave de IA/OAuth para Profile.

| Variable | Situación actual |
| --- | --- |
| `DATABASE_URL` | Obligatoria, driver `postgresql+psycopg`, host/usuario/base explícitos; sin default ni contraseña embebida en la aplicación |
| `PGPASSWORD` | Compose usa PROFILE_DB_PASSWORD para profile_runtime; no se inyecta el `.env` global ni la credencial de bootstrap |
| `AUTH_JWT_PUBLIC_KEY_PATH` | Obligatoria y absoluta; Compose monta solo la clave pública en `/app/auth_keys/public.pem`; se exige RSA pública de al menos 2048 bits |
| `AUTH_JWT_ALGORITHM` | Solo `RS256` |
| `CORS_ORIGINS` | Lista JSON de orígenes HTTP(S) explícitos, sin comodines, rutas ni credenciales; default localhost/127.0.0.1:3000. `[]` deshabilita CORS |
| `APP_ENV`, `APP_NAME`, `LOG_LEVEL` | Entorno, título y logging |
| `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_TIMEOUT_SECONDS` | Defaults 1/10/30; tamaños 1–100, min ≤ max, timeout 1–300 segundos. Pool retenido = min, overflow = max − min; no se preabren min conexiones |

Settings no lee archivos `.env`. Compose permite ajustar `PROFILE_CORS_ORIGINS`, `PROFILE_DB_POOL_MIN_SIZE`, `PROFILE_DB_POOL_MAX_SIZE` y `PROFILE_DB_TIMEOUT_SECONDS` mediante interpolación explícita; no transmite claves de IA/OAuth. Los errores de validación ocultan los valores de entrada y el repr de Settings excluye la URL DB.

El timeout se aplica a espera del pool, conexión y consultas PostgreSQL (`statement_timeout`). El engine usa pre-ping, oculta parámetros SQL, revierte sesiones con error y se libera aun si falla el arranque. La factory no crea archivos ni conexiones al importar; lifespan valida DB/esquema y clave sin preparar almacenamiento de archivos. Una dependencia inválida aborta con un mensaje genérico. `/health` indica vida del proceso; `/health/db` vuelve a comprobar dependencias y es el healthcheck de Compose. La clave se relee para detectar pérdida/cambio posterior sin cache obsoleta.

La imagen usa UID/GID 10008 sobre `python:3.12-slim`, raíz de solo lectura, sin capabilities y no-new-privileges. Solo monta la clave pública de Auth en lectura; `/tmp` es tmpfs de 16 MiB sin ejecución. Compose limita memoria a 768 MiB, CPU a 2, procesos a 128 y Uvicorn a 32 conexiones concurrentes. PROFILE-007 aplica permisos DB mínimos y registra el escaneo del artefacto y sus avisos residuales.

Para ejecución fuera de Docker, declara `DATABASE_URL` y `AUTH_JWT_PUBLIC_KEY_PATH` (ruta absoluta), instala `requirements.txt` en un entorno virtual y desde este directorio ejecuta `uvicorn app.main:create_app --factory --port 8015`. La contraseña de DB puede suministrarse por `PGPASSWORD`. No cargar un `.env` global dentro de la aplicación.

### Actualizar una instalación existente

La aplicación y la web deben actualizarse juntas: los clientes anteriores que no envían `expected_version` reciben 422. En una instancia local existente, aplica el esquema antes de arrancar la imagen nueva; un job `database-schema` ya completado no vuelve a ejecutarse por cambiar un archivo montado:

```powershell
docker compose -f docker/docker-compose.yml stop profile-service
docker compose -f docker/docker-compose.yml up -d --wait postgres
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema
docker compose -f docker/docker-compose.yml up -d --build --wait profile-service
# Reconstruye/publica también el frontend de esta misma revisión.
```

`run_all.sql` es el punto de entrada: ejecuta el preflight antes de la migración y añade `version` con valor 1 a filas existentes, sin cambiar dueño ni campos editables. La migración y su constraint positivo son repetibles; una columna de versión incompatible o valores inválidos detienen el cambio con un error genérico que requiere reparación explícita. El preflight muestra solo conteos de IDs no canónicos, identidades sin correspondencia y metadata no objeto; no vuelca valores ni borra/reasigna filas. En una instalación nueva puede indicar que Auth aún no está migrado; vuelve a consultar el inventario tras inicializar Auth:

```powershell
Get-Content -Raw scripts/database/profile/audit_profiles.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
```

Los datos que no cumplan los contratos nuevos permanecen conservados y requieren reparación explícita; la integridad compartida de identidades queda en PLAT-001. No se agrega una FK que dependa de Auth antes de sus migraciones ni se convierte un username histórico en otro dueño.

## Pruebas y auditoría

Desde la raíz, con PostgreSQL/esquema inicializados por Compose:

```powershell
docker compose -f docker/docker-compose.yml run --build --rm --no-deps profile-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps profile-tests ruff check --no-cache app tests /profile-checks
docker compose -f docker/docker-compose.yml run --build --rm --no-deps profile-audit
docker compose -f docker/docker-compose.yml run --rm --no-deps profile-tests python -m pip check
```

La suite exige `PROFILE_TEST_DATABASE_URL` explícita, provista por el servicio `profile-tests`. No crea/migra tablas ni usa uploads reales. Las escrituras HTTP quedan dentro de savepoints y una transacción exterior; al terminar se comprueba desde otra conexión que no persiste el usuario sintético. Las pruebas de pool y statement timeout usan conexiones PostgreSQL reales. Las pruebas de mantenimiento usan archivos temporales sintéticos.

El job `auth-db-roles` construye/arranca Profile, comprueba ausencia de herramientas de test/audit en runtime, ejecuta suite/Ruff/auditoría y verifica reinicio saludable. Después ejecuta el [contrato HTTP Auth–Profile](../../scripts/profile/verify_auth_contract.py) contra ambos servicios reales. El job Compose verifica la lista de variables explícitas. La suite cubre concurrencia entre conexiones, límites, identidad vigente, privacidad y recuperación de avatar.

### Comprobar tokens reales de Auth

Con Auth y Profile saludables, desde la raíz:

```powershell
docker compose -f docker/docker-compose.yml cp scripts/profile/verify_auth_contract.py auth-service:/tmp/profile-auth-contract.py
docker compose -f docker/docker-compose.yml exec -T auth-service python /tmp/profile-auth-contract.py
```

El script solo admite `AUTH_ENV=development`. Crea tres identidades y un tenant sintéticos, usa login y refresh HTTP reales, comprueba aislamiento de rutas incluso para tenant admin/superadmin y prueba revocación por contraseña, desactivación y eliminación. No imprime tokens ni contraseñas; sin PROFILE_PROBE_MARKER no escribe perfiles ni avatares. El `finally` elimina y verifica sus identidades, tenant y presupuestos de login por cuenta; conserva el presupuesto compartido del origen para respetar la protección de Auth. Los tokens pendientes de sus usuarios se limpian por cascada de Django. No ejecutarlo en producción ni interrumpirlo durante la limpieza.

Las regresiones PostgreSQL usan JWT sintéticos compatibles con Auth, usuarios efímeros y rollback; verifican también que no queden identidades ni perfiles propios de la prueba. Las consultas de identidad que fallen se cierran con 503, sin permitir la operación del perfil. La suite complementa la sonda con concurrencia entre conexiones, fallos de commit y recreación de la aplicación sobre datos confirmados.

## Avatar privado y mantenimiento

`/static` se retira y devuelve 404. GET de perfil devuelve únicamente una referencia relativa propia `/api/v1/profile/avatar?version=N` o null; no refleja Host ni URLs heredadas. La misma referencia sirve los bytes del dueño autenticado, nunca identifica a otra persona. Todas las operaciones de perfil/avatar requieren JWT vigente. La imagen responde `image/jpeg`, `private, no-store`, `nosniff` y nombre fijo `avatar.jpg`. La página y Sidebar descargan mediante el cliente autorizado, aceptan solo la ruta propia y liberan el object URL al cambiar sesión, versión o desmontar; no usan HTML generado. Cambiar la foto guarda inmediatamente sin descartar los campos de contacto aún editados. PROFILE-006 completa los estados de sesión/formulario.

Multipart admite exactamente un archivo y una versión decimal canónica; archivo máximo 5 MiB y sobre HTTP máximo 5 MiB + 64 KiB, contando bytes reales incluso sin Content-Length. El nombre/MIME enviados no determinan el contenido guardado. Se aceptan JPEG, PNG y WebP de un frame, máximo 12 millones de píxeles y 8192 por eje. Se aplica orientación EXIF, reducción a 1024 por eje y composición sobre blanco; un JPEG nuevo elimina metadata y bytes anexos, con máximo 1 MiB. Dos slots por proceso acotan parseo/normalización/escritura; saturación devuelve 503. Inválido devuelve 400/422, exceso 413 y conflicto de versión 409, sin reintento automático.

Se elige `bytea` en PostgreSQL para estas imágenes pequeñas: bytes, asociación y versión se confirman/revierten juntos. No hay archivos nuevos huérfanos ante un commit fallido ni coordinación disco/DB. El reemplazo y borrado retiran los bytes anteriores en la misma transacción; GET libera el lock de identidad antes de enviar la respuesta. El coste es hasta 1 MiB por usuario más versiones físicas de PostgreSQL y backups; administrar VACUUM/retención y capacidad como parte de la DB. El borrado lógico no promete borrado seguro de backups. `avatar_data` se carga diferido para no incluirlo en GET JSON. El constraint exige consistencia entre bytes, indicador y tamaño.

`run_all.sql` incluye [avatars.sql](../../scripts/database/profile/avatars.sql) después de versiones. Es aditivo/repetible: conserva las URLs anteriores y agrega `avatar_data=NULL`, `avatar_ready=FALSE`. No descarga URL externas ni deduce dueño por un nombre público antiguo. Las referencias heredadas se ocultan en API hasta revisión/importación o nueva carga del dueño; los archivos de origen se conservan. Actualizar esquema, servicio y web juntos según el procedimiento anterior. Un rollback posterior debe restaurar la revisión privada compatible y su backup; no volver a publicar `/static` ni la imagen anterior con datos personales.

### Importar fuentes antiguas con revisión explícita

La alternativa preferida es que cada dueño cargue otra vez su foto. Si se requiere preservar una fuente antigua, un operador debe verificar por separado su pertenencia: una URL pública previa **no prueba propiedad**. Mantén backup, revisa referencias compartidas, confirma ID Auth activo, versión y checksum. No ensayes sobre uploads reales. Las herramientas de mantenimiento no se ejecutan al arrancar la API y usan `PROFILE_MIGRATION_DATABASE_URL` separado del runtime.

El servicio optativo `profile-avatar-tools` monta `uploads/profile` únicamente en lectura. Los comandos siguientes se ejecutan desde la raíz; requieren permisos de lectura para UID 10008 y un manifest absoluto revisado fuera del repositorio. No concedas escritura al origen. Monta solo el directorio de manifiestos necesario:

```powershell
docker compose -f docker/docker-compose.yml --profile maintenance run --build --rm --no-deps profile-avatar-tools
# Solo conteos: avatares privados, referencias antiguas, fuentes compartidas y huérfanos.
docker compose -f docker/docker-compose.yml --profile maintenance run --rm --no-deps -v "${PWD}/reviewed-avatar-manifests:/reviewed:ro" profile-avatar-tools python -m app.maintenance.avatars import --legacy-dir /legacy-avatars --manifest /reviewed/import.json
# Revisar conteos antes de repetir con --apply; sin él no modifica datos.
```

Cada entrada de `import.json` contiene `user_id` entero, `expected_version` positiva, `source` (32 hex minúsculos + extensión jpg/jpeg/png/webp), `sha256` (64 hex) y `legacy_url` exacta actual. La ruta URL debe corresponder a `/static/{source}`, sin credenciales/query/fragmento; no se accede a su host. Máximo 100 dueños y fuentes distintos por lote, manifest 64 KiB. Se abren directorios por descriptores sin seguir enlaces de ningún componente; solo archivos regulares con un enlace y tamaño acotado, sin traversal, hardlinks ni FIFO. La lectura está vinculada al descriptor, no a comprobaciones de ruta seguidas de una reapertura. Checksum y normalización de todo el lote preceden a las escrituras. Cada actualización exige dueño activo, versión, URL exacta y ausencia de avatar privado; los no elegibles se omiten y se cuentan. Un fallo revierte las escrituras del lote. La herramienta nunca elimina fuentes.

### Retirar bytes de perfiles sin identidad

Inventaría primero, revisa backup y retención, y prepara `prune.json` con IDs/versiones de perfiles realmente huérfanos. Usa el mismo comando sustituyendo `import` por `prune` y el manifest correspondiente. Sin `--apply` solo cuenta; con él retira avatar/URL e incrementa versión, preservando contacto/metadata. No actúa sobre cuentas existentes, incluidas inactivas, ni versiones cambiadas. No ejecutarlo durante restauraciones administrativas de identidades. La integridad referencial general sigue en PLAT-001. Los archivos históricos requieren una decisión de retención independiente; no hay borrado masivo.

### Sonda HTTP de avatar con Auth real

Para probar también carga/reemplazo/borrado, usa un nonce nuevo y limpieza SQL en finally. Ejemplo PowerShell desde la raíz (sobre un entorno de desarrollo sintético con Auth y Profile saludables):

```powershell
docker compose -f docker/docker-compose.yml cp scripts/profile/verify_auth_contract.py auth-service:/tmp/profile-auth-contract.py
if ($LASTEXITCODE -ne 0) { throw "No se pudo preparar la sonda" }
$profileProbeMarker = [guid]::NewGuid().ToString("N")
try {
  docker compose -f docker/docker-compose.yml exec -T -e "PROFILE_PROBE_MARKER=$profileProbeMarker" auth-service python /tmp/profile-auth-contract.py
  if ($LASTEXITCODE -ne 0) { throw "Falló la sonda HTTP" }
} finally {
  Get-Content -Raw scripts/profile/cleanup_probe.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1 -v "probe_marker=$profileProbeMarker"
  if ($LASTEXITCODE -ne 0) { throw "Limpieza sintética incompleta; revisar antes de repetir" }
}
```

Sin marcador, el script mantiene la sonda de lectura. CI usa la misma coordinación mediante un trap de bash. El SQL solo retira perfiles marcados cuyo usuario Auth ya no existe y falla si queda alguno; el finally del script elimina primero identidades, tenant y presupuestos por cuenta. No reutilizar el marcador ni omitir la limpieza; no se imprimen cuerpos personales ni tokens.

La suite permanente cubre aislamiento incluso con roles administrativos, límites/códecs/metadata, conflictos entre conexiones, fallo de commit y recuperación tras reinicio, esquema repetido y constraint, confinamiento e importación dry-run/aplicada y retirada de huérfanos. Frontend prueba contrato multipart/DELETE, rechazo de URL externa, aborto de respuestas tardías y revocación de object URLs. PROFILE-006 incorpora pruebas Chromium; PROFILE-007 registra el escaneo de SO y sus seguimientos.

## Sesión y edición web

El cliente de perfil y el cliente Auth conservan su identidad durante la renovación del access token, consultan la credencial actual y comparten la renovación entre peticiones simultáneas de cada cliente. Un identificador local de sesión nuevo por login/carga inicial, junto al usuario y tenant activo, delimita el editor; no es una credencial ni una garantía de autorización del servidor. Logout, nueva cuenta o cambio de tenant invalida clientes anteriores y remonta el editor, sin conservar contactos, contraseñas ni foto de otra sesión. Respuestas de una sesión anterior se descartan incluso si devuelven 200; un 401 anterior no renueva ni cierra la cuenta nueva.

El controlador del editor cancela GET/PUT/upload/DELETE al desmontar, invalida respuestas tardías y serializa carga/recarga/guardado/foto. Abortar una petición no deshace un commit ya realizado en el servidor: al volver a abrir se lee la versión vigente. No hay reintentos de conflictos. El formulario mantiene una instantánea separada del perfil confirmado: una foto cambia la versión usada por el próximo guardado sin reemplazar el borrador de contacto. Un fallo conserva ese borrador; solo guardar con éxito o **Descartar cambios y recargar perfil** reemplaza sus campos. Renovar JWT o actualizar `/me` no repuebla el formulario. El perfil global rechaza versiones anteriores, incluida una carga que termine después de un guardado.

**Correo de contacto** es editable y distinto del correo de identidad de Auth, que se muestra como referencia. La vista de permisos enumera los códigos efectivos de Auth, el rol y grupos del tenant activo; no infiere permisos por palabras, staff o grupos globales, ni utiliza las listas históricas de Profile como autoridad. La autorización final pertenece al servicio correspondiente. Cambiar contraseña usa Auth, impide doble envío y limpia los campos al confirmar el cambio; tras éxito ofrece cerrar sesión y volver a ingresar, porque Auth revoca las credenciales anteriores. Los errores no se imprimen con cuerpos o contraseñas en consola.

Desde `frontend`, ejecuta:

```powershell
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

CI instala Chromium con `npx playwright install --with-deps chromium`. La configuración inicia Vite exclusivamente en `127.0.0.1:4173`, con APIs interceptadas y datos sintéticos, sin IA/OAuth ni acceso a backend real. Las pruebas de lógica cubren respuestas antiguas, reinicio del controlador, refresh, sesión sustituida, conflictos y exclusión entre escrituras; Chromium verifica conservación del borrador durante refresh/upload, doble submit, recuperación explícita de conflictos, email independiente, límites locales y permisos/semántica accesible. No sustituyen la sonda real de Auth/PostgreSQL de PROFILE-005 ni una auditoría completa de accesibilidad o frontend (WEB-001). La evidencia de permisos DB y artefacto se detalla en [operación](#rol-postgresql-y-operación).

## Rol PostgreSQL y operación

Compose usa `profile_runtime` y `PROFILE_DB_PASSWORD` (valor de desarrollo en `.env.example`). `profile-db-role` espera esquema y Auth saludable: la tabla de identidad debe existir antes de conceder columnas. El job administrativo monta solo los SQL de Profile; la API no recibe su credencial de bootstrap ni la de mantenimiento de avatares. En una instalación existente, tras aplicar el esquema y arrancar Auth, provisiona antes de iniciar la imagen nueva:

```powershell
docker compose -f docker/docker-compose.yml stop profile-service
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema
docker compose -f docker/docker-compose.yml up -d --wait auth-service
docker compose -f docker/docker-compose.yml run --rm --no-deps profile-db-role
docker compose -f docker/docker-compose.yml up -d --build --wait profile-service
```

Para rotar `PROFILE_DB_PASSWORD`, actualiza el entorno, detén Profile, repite el job y recrea el servicio con la misma configuración. No ejecutes pruebas/mantenimiento con datos personales ni reutilices el rol runtime para migrar. El mantenimiento revisado de avatares sigue usando su credencial administrativa independiente.

| Principal | Permisos efectivos |
| --- | --- |
| `profile_runtime` | SELECT en `user_profiles`; INSERT de dueño/contacto/metadata/avatar; UPDATE de contacto/metadata/avatar/versión. Sin DELETE, cambio de dueño/PK/timestamps, acceso directo a Auth/documentos, secuencias ni CREATE en public |
| `profile_identity_owner` | NOLOGIN; SELECT únicamente id/activo/contraseña codificada de Auth y UPDATE(id), requerido por PostgreSQL para `FOR SHARE`. Sin membresías que permitan asumirlo desde runtime; su única función no modifica Auth ni devuelve columnas de identidad |
| `profile_identity_is_current(bigint,text)` | SECURITY DEFINER, VOLATILE, STRICT; devuelve solo booleano, compara la huella y conserva `FOR SHARE` hasta terminar la transacción del caller. Objetos públicos cualificados, search_path fijo `pg_catalog, pg_temp`, sin EXECUTE para PUBLIC; ejecución concedida al runtime |

Ambos roles carecen de superusuario, creación de roles/bases, herencia, replicación y bypass RLS. El rol runtime es compartido por el servicio: la privacidad por dueño se aplica en JWT/repositorio, **no mediante RLS personal**. Las restricciones generales de identidad/tenants permanecen en PLAT-001. Readiness ejecuta la función con ID inexistente y verifica columnas de perfil y clave pública; no requiere leer contraseñas directamente.

[provision_role.sql](../../scripts/database/profile/provision_role.sql) es transaccional y repetible, usa el bloqueo global de aprovisionamiento y ejecuta [verify_role.sql](../../scripts/database/profile/verify_role.sql). Este compara permisos efectivos por columna/operación, atributos, membresías, secuencias y ACL/configuración de la función; detecta también acceso inesperado a otros helpers privilegiados. Permisos excesivos detienen el job y requieren revisión explícita; no revoca permisos ajenos indiscriminadamente. La suite verifica denegaciones y deriva de grants con rollback, login real del runtime (incluido rechazo de SET ROLE), HTTP propio y concurrencia con revocación en ambos órdenes.

### Evidencia del artefacto

[IMAGE_AUDIT.json](docs/IMAGE_AUDIT.json) conserva IDs de Docker/escáner, SHA-256 del archivo exportado, base, inventario Python y hallazgos del artefacto vigente, derivados de la auditoría transversal. El análisis inicial fue el 7 de noviembre de 2026. Se reconstruyeron las etapas con `--pull --no-cache`; tras encontrar corrección disponible, se añadió actualización de `zlib1g` desde Debian Security. La imagen final instala `1:1.3.dfsg+really1.3.1-1+deb13u1`; Trivy 0.76.2 ya no informa CVE-2026-76844 ni CVE-2026-85091, y CI exige esa versión mínima. El runtime sigue UID/GID 10008, readonly, sin uploads y sin pytest/Ruff/httpx/pip-audit. `pip check` y la auditoría del inventario Python instalado pasan sin avisos conocidos.

El escaneo final de severidades HIGH/CRITICAL registra **47 coincidencias altas de Debian, correspondientes a 11 CVE distintos, cero críticos y ninguna versión corregida indicada para esos avisos del SO**. Se mantienen en PROFILE-F01/PLAT-002: reconstruir y reevaluar antes de despliegue público. No se declara la imagen libre de riesgos ni se validó explotación de cada coincidencia.

El escaneo histórico registraba **CVE-2025-47273** en la declaración vendorizada `setuptools==70.3.0` de pip 26.3 e indicaba 78.1.1. La entrega actual retira pip y ensurepip completos del runtime; no intenta corregir esa copia instalando otro setuptools ni aplica supresiones. PROFILE-F02 se reevalúa con el artefacto final de PLAT-002. Esta distinción explica por qué la auditoría de distribuciones instaladas y el escaneo histórico mostraban resultados diferentes.

Para repetir el escaneo sin montar el socket Docker (bash, desde la raíz):

```sh
docker build --pull --no-cache -t blandskron-profile-audit backend/ProfileServices
audit_dir="$(mktemp -d)"
docker save -o "$audit_dir/runtime.tar" blandskron-profile-audit
docker run --rm -v "$audit_dir:/audit" -v blandskron-trivy-cache:/root/.cache/trivy aquasec/trivy:0.76.2 image --scanners vuln --severity HIGH,CRITICAL --format json --output /audit/trivy.json --input /audit/runtime.tar
```

Usa archivos temporales fuera de Git; los reportes dependen de la base de avisos y del artefacto del momento. La evidencia no es un escaneo de secretos ni una auditoría exhaustiva del código. CI vuelve a comprobar arranque, repetición, permisos e imagen.

## Cierre del servicio

PROFILE-008 revisa rutas, consumidores web, esquema, privilegios, mantenimiento y archivos. Se retiraron cuatro excepciones sin consumidores (`NotFoundError`, `ValidationError`, `ExternalServiceError`, `DatabaseError`) y dos manejadores HTTP inalcanzables. Se conservan `AppError`/`ConflictError`, los contratos probados, migraciones, preflight, herramientas de mantenimiento y evidencia. El diagnóstico histórico y las decisiones propuestas se sustituyeron por esta operación final; su trazabilidad permanece en Git y el tablero. `docs/` solo conserva evidencia documental; el código está en `app/`, `tests/` y `scripts/`.

Validación de cierre del 7 de noviembre de 2026:

- **217 pruebas PostgreSQL**, Ruff, pip check/audit y Compose aprobados. OpenAPI verifica exactamente cinco rutas, métodos propios autenticados, multipart y JPEG privado. Las pruebas incluyen conflictos entre conexiones, revocación en ambos órdenes con rol mínimo, rollback de commit y recuperación del avatar al recrear la aplicación sobre datos confirmados.
- **81 pruebas frontend y tres escenarios Chromium**, con npm ci/test/build aprobados. Las APIs interceptadas del navegador verifican borrador durante refresh/upload, doble submit, conflicto/recarga, correo independiente, límites, permisos y selector de foto por teclado.
- **36 módulos importados** sin ejecutar el arranque. Instalación aislada con volúmenes nuevos; sonda HTTP con JWT reales para tres usuarios/roles, fotos distintas por dueño, reemplazo/borrado, revocación y limpieza SQL de los tres perfiles sintéticos. Reaprovisionamiento y reinicio saludable sobre el mismo volumen.
- Auditoría actualizada al artefacto final en [IMAGE_AUDIT.json](docs/IMAGE_AUDIT.json), sin cambio de los avisos residuales. Se preservan fuentes y filas heredadas; no se montaron uploads personales ni se ejecutaron IA/OAuth reales.

El cierre funcional quedó integrado mediante PR #66. Permanecen PROFILE-F01/F02 (imagen), PLAT-001 (integridad compartida), PLAT-002 (reevaluación del conjunto) y WEB-001 (frontend general, incluidas cuatro alertas npm). Estos seguimientos no se cierran por finalizar Profile. El siguiente microservicio es DocumentExportServices mediante EXPORT-001; la entrega global sigue pendiente.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
