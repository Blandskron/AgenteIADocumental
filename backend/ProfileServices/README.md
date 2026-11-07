# ProfileServices

Servicio FastAPI de perfil y avatar de Blandskron Documental, publicado localmente en `http://localhost:8015`. AuthServices administra identidad, credenciales y membresías; Profile guarda contacto, presentación y avatar privado en `user_profiles` (PostgreSQL).

**Estado:** PROFILE-001 a PROFILE-004 integrados (PR #59 a #62). PROFILE-005 entrega avatar privado transaccional y su consumidor web. PROFILE-006 entrega edición estable durante refresh, aislamiento de sesiones y permisos efectivos con pruebas Chromium; PROFILE-007 entrega rol DB acotado, helper de identidad y evidencia de imagen; el cierre sigue en PROFILE-008. Runtime ya usa UID/GID 10008 y no monta uploads. El [diagnóstico histórico](#diagnóstico-profile-001) describe la línea base, no las garantías actuales. El estado vive en el [tablero](../../ROADMAP.md#profileservices).

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

`tests/` contiene la suite permanente y CI la ejecuta sobre PostgreSQL. Las etapas Docker `runtime`, `test` y `audit` separan las herramientas del servicio; el inventario auditado se captura antes de instalar pip-audit. No hay aplicación Django ni código Python dentro de una carpeta documental que sea necesario trasladar.

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

**Transición de contrato:** se retiran `GET /api/v1/profiles`, `GET /api/v1/profiles/{user_id}` y `PUT /api/v1/profiles/{user_id}`. Devuelven 404 y no figuran en OpenAPI, incluso para el propio ID o administradores. La búsqueda de consumidores no encontró usos en la web; las integraciones externas deben usar `/api/v1/profile` con la sesión del dueño. Los tokens anteriores sin los claims requeridos se rechazan; renueva la sesión en Auth. No se migran ni borran perfiles históricos: registros asociados a username o IDs no canónicos requerirán inventario y reparación explícita en PROFILE-004.

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

El runtime no monta `uploads/profile`; los avatares privados residen en PostgreSQL. Solo la herramienta optativa de mantenimiento monta las fuentes antiguas en lectura. Las pruebas usan directorios sintéticos temporales y rollback; la comprobación histórica de PROFILE-002 usó un volumen Docker separado. No se necesita clave de IA/OAuth para Profile.

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
docker compose -f docker/docker-compose.yml exec -T profile-service python -m pip check
```

La suite exige `PROFILE_TEST_DATABASE_URL` explícita, provista por el servicio `profile-tests`. No crea/migra tablas ni usa uploads reales. Las escrituras HTTP quedan dentro de savepoints y una transacción exterior; al terminar se comprueba desde otra conexión que no persiste el usuario sintético. Las pruebas de pool y statement timeout usan conexiones PostgreSQL reales. Las pruebas de mantenimiento usan archivos temporales sintéticos.

El job `auth-db-roles` construye/arranca Profile, comprueba ausencia de herramientas de test/audit en runtime, ejecuta suite/Ruff/auditoría y verifica reinicio saludable. Después ejecuta el [contrato HTTP Auth–Profile](../../scripts/profile/verify_auth_contract.py) contra ambos servicios reales. El job Compose verifica la lista de variables explícitas. La concurrencia de escrituras, límites y privacidad de archivos permanecen en sus tarjetas.

PROFILE-002 actualiza FastAPI/Starlette, PyJWT, cryptography, python-dotenv, Pillow y python-multipart, conservando el resto del conjunto compatible. La auditoría consulta el inventario de runtime antes de instalar herramientas; no confundir ese resultado con un escaneo de SO o de copias vendorizadas (PROFILE-007). TestClient emite una advertencia sobre la futura migración de httpx a httpx2, limitada a la etapa de pruebas.

Evidencia local de PROFILE-002 (6 de noviembre de 2026): **52 pruebas aprobadas**, Ruff y pip check aprobados; `profile-audit` sin avisos conocidos, sin supresiones. Se construyeron las tres etapas con proyecto `library008-release`, se comprobó la lista de variables/CORS/montaje de clave/healthcheck y se validó arranque y reinicio contra PostgreSQL existente y clave pública real de Auth, con volumen sintético separado. Runtime no contiene pytest/Ruff/httpx/pip-audit. No se usaron avatares reales ni se ejecutó OAuth, IA, navegador o un flujo de login con JWT real en esta tarjeta. CI verifica además el arranque sobre su instalación nueva; el estado de su ejecución se registra en el PR.

### Comprobar tokens reales de Auth

Con Auth y Profile saludables, desde la raíz:

```powershell
docker compose -f docker/docker-compose.yml cp scripts/profile/verify_auth_contract.py auth-service:/tmp/profile-auth-contract.py
docker compose -f docker/docker-compose.yml exec -T auth-service python /tmp/profile-auth-contract.py
```

El script solo admite `AUTH_ENV=development`. Crea tres identidades y un tenant sintéticos, usa login y refresh HTTP reales, comprueba aislamiento de rutas incluso para tenant admin/superadmin y prueba revocación por contraseña, desactivación y eliminación. No imprime tokens ni contraseñas; sin PROFILE_PROBE_MARKER no escribe perfiles ni avatares. El `finally` elimina y verifica sus identidades, tenant y presupuestos de login por cuenta; conserva el presupuesto compartido del origen para respetar la protección de Auth. Los tokens pendientes de sus usuarios se limpian por cascada de Django. No ejecutarlo en producción ni interrumpirlo durante la limpieza.

Las regresiones PostgreSQL usan JWT sintéticos compatibles con Auth, usuarios efímeros y rollback; verifican también que no queden identidades ni perfiles propios de la prueba. Las consultas de identidad que fallen se cierran con 503, sin permitir la operación del perfil. Estos checks no sustituyen las pruebas de concurrencia ni de avatar de las tarjetas siguientes.

PROFILE-004 añade pruebas con conexiones independientes y esperas de lock observadas en PostgreSQL, creación/update concurrentes y revalidación de cuenta tras revocaciones en ambos órdenes. Esos escenarios crean registros sintéticos confirmados mediante commit entre conexiones y los eliminan/verifican al terminar; no usan rollback como sustituto de visibilidad entre sesiones. Una tabla temporal con esquema anterior verifica preflight, conservación de valores y segunda ejecución de la migración. PROFILE-005 añade pruebas del ciclo privado de avatar.

Evidencia local de PROFILE-003: **112 pruebas aprobadas**, Ruff sobre app/tests/script, pip check, Compose y enlaces aprobados; auditoría runtime sin avisos conocidos. El contrato HTTP real de arriba pasó con usuario normal, tenant admin y superadmin, login y refresh, cambio de contraseña, cuenta inactiva/eliminada y limpieza verificada. Se conservaron los datos existentes y se usó el volumen sintético de Profile; el estado de CI y la revisión se registran en el PR.

Evidencia local de PROFILE-004 (7 de noviembre de 2026): **170 pruebas backend y 64 frontend aprobadas**, npm ci/test/build, Ruff, pip check y auditoría runtime sin avisos conocidos. Se validó la instalación local con volúmenes nuevos, el esquema anterior en tabla temporal y el contrato HTTP real con Auth (incluye versión 0, 422 sin versión y 409 sin escritura). Tras la limpieza, el preflight del entorno sintético informa cero IDs no canónicos, cero metadata no objeto y cero perfiles sin identidad. El directorio real de avatares no se montó. Persisten las cuatro alertas altas npm de WEB-001 y la advertencia TestClient httpx/httpx2; no se ha ejecutado aún la revisión integral de navegador ni el escaneo de SO de PROFILE-007. CI/revisión se registran en el PR.

## Avatar privado y mantenimiento (PROFILE-005)

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

Sin marcador, `verify_auth_contract.py` mantiene la sonda de lectura. Para probar también carga, reemplazo, lectura y borrado, CI genera un nonce `PROFILE_PROBE_MARKER` de 32 hex, lo pasa al contenedor Auth y ejecuta siempre [cleanup_probe.sql](../../scripts/profile/cleanup_probe.sql) en un `finally`/trap con `psql -v probe_marker=NONCE`. El SQL solo elimina perfiles sintéticos con ese marcador y sin usuario Auth, y falla si queda alguno. No reutilizar el marcador ni omitir esa limpieza. Las identidades se retiran primero en el finally del script. No se imprimen cuerpos personales ni tokens.

La suite permanente cubre aislamiento incluso con roles administrativos, límites/códecs/metadata, conflictos entre conexiones, fallo de commit y recuperación tras reinicio, esquema repetido y constraint, confinamiento e importación dry-run/aplicada y retirada de huérfanos. Frontend prueba contrato multipart/DELETE, rechazo de URL externa, aborto de respuestas tardías y revocación de object URLs. PROFILE-006 incorpora pruebas Chromium; PROFILE-007 registra el escaneo de SO y sus seguimientos.

## Sesión y edición web (PROFILE-006)

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

CI instala Chromium con `npx playwright install --with-deps chromium`. La configuración inicia Vite exclusivamente en `127.0.0.1:4173`, con APIs interceptadas y datos sintéticos, sin IA/OAuth ni acceso a backend real. Las pruebas de lógica cubren respuestas antiguas, reinicio del controlador, refresh, sesión sustituida, conflictos y exclusión entre escrituras; Chromium verifica conservación del borrador durante refresh/upload, doble submit, recuperación explícita de conflictos, email independiente, límites locales y permisos/semántica accesible. No sustituyen la sonda real de Auth/PostgreSQL de PROFILE-005 ni una auditoría completa de accesibilidad o frontend (WEB-001). La evidencia de permisos DB y artefacto se detalla en PROFILE-007.

## Rol PostgreSQL y operación (PROFILE-007)

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

[IMAGE_AUDIT.json](docs/IMAGE_AUDIT.json) conserva IDs de Docker/escáner, SHA-256 del archivo exportado, base, inventario Python y hallazgos del 7 de noviembre de 2026. Se reconstruyeron las etapas con `--pull --no-cache`; tras encontrar corrección disponible, se añadió actualización de `zlib1g` desde Debian Security. La imagen final instala `1:1.3.dfsg+really1.3.1-1+deb13u1`; Trivy 0.76.2 ya no informa CVE-2026-76844 ni CVE-2026-85091, y CI exige esa versión mínima. El runtime sigue UID/GID 10008, readonly, sin uploads y sin pytest/Ruff/httpx/pip-audit. `pip check` y la auditoría del inventario Python instalado pasan sin avisos conocidos.

El escaneo final de severidades HIGH/CRITICAL registra **47 coincidencias altas de Debian, correspondientes a 11 CVE distintos, cero críticos y ninguna versión corregida indicada para esos avisos del SO**. Se mantienen en PROFILE-F01/PLAT-002: reconstruir y reevaluar antes de despliegue público. No se declara la imagen libre de riesgos ni se validó explotación de cada coincidencia.

Trivy registra además **CVE-2025-47273** en la declaración vendorizada `setuptools==70.3.0` de pip 26.3 e indica 78.1.1. No hay distribución setuptools instalada; sí existe la copia vendorizada de `pkg_resources`. PyPI reportaba pip 26.3 como última versión disponible. Instalar otra distribución setuptools no reemplaza esa copia. PROFILE-F02 conserva el seguimiento upstream y la reevaluación, sin supresión ni conclusión automática de falso positivo. Esta distinción explica por qué la auditoría de distribuciones instaladas y Trivy muestran resultados diferentes.

Para repetir el escaneo sin montar el socket Docker (bash, desde la raíz):

```sh
docker build --pull --no-cache -t blandskron-profile-audit backend/ProfileServices
audit_dir="$(mktemp -d)"
docker save -o "$audit_dir/runtime.tar" blandskron-profile-audit
docker run --rm -v "$audit_dir:/audit" -v blandskron-trivy-cache:/root/.cache/trivy aquasec/trivy:0.76.2 image --scanners vuln --severity HIGH,CRITICAL --format json --output /audit/trivy.json --input /audit/runtime.tar
```

Usa archivos temporales fuera de Git; los reportes dependen de la base de avisos y del artefacto del momento. La evidencia no es un escaneo de secretos ni una auditoría exhaustiva del código. Se validaron instalación aislada con volúmenes nuevos, actualización/reaprovisionamiento y reinicio sobre volumen existente, 217 pruebas PostgreSQL, Ruff, pip check/audit y contrato HTTP con JWT reales (tres roles, perfil/fotos/revocación y limpieza SQL de los tres perfiles). CI vuelve a comprobar arranque, repetición, permisos e imagen. El cierre documental/funcional final sigue en PROFILE-008.

## Diagnóstico PROFILE-001

**Evidencia histórica del 6 de noviembre de 2026, commit `1776a6f`.** Las observaciones de configuración/dependencias/salud siguientes corresponden a esa versión anterior a PROFILE-002 y se conservan para trazar el trabajo pendiente.

Se revisaron todos los módulos del servicio, Dockerfile, dependencias, esquema y trigger compartidos, Compose, identidad/membresías de Auth y consumidores web. La inspección se complementó con sondas TestClient sobre la imagen construida, usando PostgreSQL real del entorno local, clave RSA y usuarios sintéticos. Las escrituras se encerraron en una transacción externa con savepoints y se verificó desde otra conexión que el rollback no dejó perfiles sintéticos. Los archivos se crearon exclusivamente en `/tmp` del contenedor eliminado al terminar. No se utilizaron claves de proveedores, datos personales ni el volumen real de avatares.

### Observaciones reproducidas

| Caso sintético | Resultado en la línea base | Incremento |
| --- | --- | --- |
| Petición sin JWT / token refresh | 401 / 401 | Conservar en PROFILE-003 |
| Access firmado sin `exp`; `exp: null` | 200; 500 respectivamente | PROFILE-003 |
| `user_id` y `sub` distintos; identidad solo `username` | Ambos aceptados, 200 | PROFILE-003 |
| Identidad sin usuario en Auth | GET devuelve perfil vacío, 200; PUT permite crear | PROFILE-003/004 |
| Usuario ordinario consulta otro perfil | 403 | Conservar en PROFILE-003 |
| Tenant admin consulta/modifica un perfil sin relación de tenant | GET y PUT 200 | PROFILE-003 |
| Flag firmado `is_superadmin: "false"` | Se considera verdadero y permite listado, 200 | PROFILE-003 |
| Listado con `limit=1` y dos perfiles sintéticos | Ignora parámetro y devuelve al menos dos | PROFILE-003 |
| Email inválido, teléfono de 10.000 caracteres y URL `javascript:synthetic` | PUT 200; campo desconocido ignorado | PROFILE-004 |
| `email: null` y objeto parcial de metadata | Email conservado; objeto anterior reemplazado | PROFILE-004 |
| Archivo que no es imagen | 400 | Conservar en PROFILE-005 |
| PNG de 2×2 con bytes sintéticos anexos que supera 5 MiB | Upload 200; nombre generado `.png`; bytes originales conservados | PROFILE-005 |
| Descargar ese archivo sin JWT | 200 | PROFILE-005/006 |
| Header Host sintético en upload | Determina el origen de la URL devuelta | PROFILE-002/005 |
| Salud DB y petición con Origin externo | 200 y `Access-Control-Allow-Origin: *` | PROFILE-002 |

Los JWT malformados de estas sondas están **firmados por la clave sintética confiada en el contenedor**. No demuestran falsificación de firmas ni que Auth emita esos claims; demuestran falta de validación defensiva en Profile. El escenario admin no comprobó una matriz completa de tenants activos/revocados; la autorización actual no consulta esas relaciones.

### Riesgos identificados por lectura, todavía sin prueba específica

- La creación usa SELECT y luego INSERT sin resolver carreras sobre `user_id` único. Dos primeras escrituras simultáneas pueden competir; las actualizaciones y la metadata no tienen control de versión. Hace falta prueba con sesiones separadas.
- No hay FK de perfil a Auth ni comprobación de usuario activo. La eliminación de identidad puede dejar perfiles y archivos; se necesita inventario previo y política compatible con los demás escritores.
- El upload hace `file.file.read()` completo; no impone límite propio de bytes, dimensiones, frames o formatos ni recodifica. El spooling de multipart no limita esa lectura final. No se ensayó agotamiento de memoria, bomba de descompresión o carga de gran escala.
- Storage y perfil tienen dos escrituras independientes: subir sin guardar deja archivos y reemplazar no elimina la foto anterior. No existe recuperación ante fallo de disco, compensación o carrera de reemplazos.
- La web limita a 5 MiB, admite `image/*` y URLs externas libres. `<img>` consulta esas URLs directamente; la ruta privada necesitará blob autenticado y limpieza de object URLs. No se comprobó SSRF de servidor ni se afirma que exista.
- AuthProvider conserva el perfil anterior mientras carga una sesión nueva; el GET tiene guardia de desmontaje, pero save/upload no invalidan resultados tardíos por identidad. La página puede repoblar campos al cambiar `currentUser` y usa `innerHTML` como fallback de imagen. Requiere pruebas de sesión, renovación, edición y error; no se afirma una explotación XSS demostrada.
- La matriz visual de permisos deduce acciones por coincidencias de texto y concede todas a `isStaff`. No representa necesariamente los permisos efectivos del tenant activo ni concede permisos en el backend; debe alinearse con los contratos vigentes.
- Excepciones de aplicación reflejan `str(exc)`; errores SQL no están traducidos. Revisar respuestas y logs sin guardar cuerpos ni datos personales. El trigger ya mantiene `updated_at`; no duplicarlo con otra fuente de tiempo sin necesidad.

### Evidencia de herramientas y límites

Comandos ejecutados desde la raíz (proyecto local para no interferir con otras instalaciones):

```powershell
docker compose -f docker/docker-compose.yml -p library008-release build profile-service
docker run --rm --network none library008-release-profile-service python -m pip check
docker run --rm --network none library008-release-profile-service ruff check --no-cache app
docker run --rm --network none library008-release-profile-service python -c 'import os; print(os.geteuid())'
docker compose -f docker/docker-compose.yml config --quiet
```

Build, pip check, Ruff y Compose aprobados; UID observado: **0**. Imagen local: `sha256:f987b0ee524a46832e503bbba47ade6fe3c12703d3eb51675dd1b36eaeb30e37` (manifest list); config `sha256:9dca9055c706ba857d6d16d84636861de4ad32f9626dbcca4f043413a2e7e1c9`. La etiqueta y sus transitivas pueden cambiar al reconstruir; esos identificadores describen esta ejecución.

Las sondas utilizaron `httpx==0.28.1` instalado solo en un contenedor descartable y un script temporal retirado tras documentar resultados. Son evidencia exploratoria, **no una suite permanente ni un gate aprobado de Profile**. PROFILE-002/003/005 incorporarán casos mantenidos y regresiones. No se arrancó el stack completo, no se probó navegador, JWT real de Auth, concurrencia ni restauración de datos en esta tarjeta.

Para auditar se congelaron primero los paquetes de la imagen con `pip freeze > /tmp/baseline.txt`; después se instaló `pip-audit==2.9.0` solo en ese contenedor y se ejecutó `pip-audit --disable-pip --no-deps -r /tmp/baseline.txt`. Reportó **92 avisos en siete paquetes**: cryptography 46.0.6, Pillow 11.2.1, PyJWT 2.12.1, pytest 8.3.5, python-dotenv 1.1.0, python-multipart 0.0.20 y Starlette 0.46.2. Incluye IDs PYSEC/GHSA potencialmente relacionados: no es un conteo de CVE únicos ni prueba de explotación. La mayoría indica versiones corregidas; PYSEC-2026-4146 no muestra corrección. Actualizar el conjunto compatible y reevaluar sin supresiones arbitrarias en PROFILE-002; pytest debe salir de runtime. El SO y copias vendorizadas se escanearán en PROFILE-007. Los seguimientos de imágenes anteriores continúan abiertos en PLAT-002.

## Decisiones propuestas para implementar por incrementos

1. Mantener este servicio pequeño y separado de Auth: contacto/presentación aquí; contraseña, identidad, roles y membresías en Auth. No agregar frameworks, capas ni storage remoto sin una necesidad demostrada.
2. Hacer privado el perfil por dueño, incluso frente a administradores de documentos. La web no consume listado ni perfiles ajenos; retirar esa superficie con una transición explícita. Un directorio empresarial necesitaría una política y respuesta mínima propias, no acceso al perfil personal completo.
3. Validar identidad y vigencia contra Auth sin copiar su modelo de autorización. Definir campos, límites y actualización parcial antes de migrar; conservar datos históricos mediante inventario y reparación explícita.
4. Avatar local asociado al dueño, lectura autenticada y recodificación. Propuesta inicial: hasta 5 MiB para coincidir con la UI; concretar formato, píxeles, dimensiones y frames en PROFILE-005 mediante pruebas. Una operación debe dejar referencia y archivo consistentes o recuperar/limpiar el fallo; inventariar URLs anteriores antes de retirar `/static`. La adaptación mínima del consumidor se entrega junto al cambio de acceso, sin dejar un incremento con avatares rotos; PROFILE-006 completa estados, carreras y experiencia web.
5. Pruebas PostgreSQL y contratos HTTP en CI, consumidor web probado con cambios de sesión, rol DB mínimo e imagen sin root. Cerrar después de validar instalación nueva, actualización y artefacto final con seguimientos visibles.

El orden y los criterios están en [PROFILE-002 a PROFILE-008](../../ROADMAP.md#profileservices). PROFILE-002 incorpora la base de configuración/dependencias/pruebas; este análisis no cierra Profile.

Referencias consultadas: [Agents First Framework](https://github.com/Blandskron/agents-first-repo-docs) para contexto verificable y documentación sin duplicación; [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/#uploadfile) para spooling y lectura; [Pillow Image.verify](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify) para diferenciar verificación de decodificación. Las decisiones se basan en este código y sus sondas, no en una certificación del framework.
