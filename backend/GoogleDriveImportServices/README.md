# GoogleDriveImportServices

Microservicio responsable de conectar Google Drive con la biblioteca documental de Blandskron Documental.

**Estado:** cierre DRIVE-006/007/008 en revisión. Incluye identidad vigente, OAuth PKCE, diario recuperable, historial paginado y web coordinada. [Tablero](../../ROADMAP.md#googledriveimportservices), [guía para agentes](AGENTS.md), [diagnóstico histórico](docs/HISTORY.md) y [auditoría de imagen](docs/IMAGE_AUDIT.json). Google Drive sigue opcional y deshabilitado por defecto.

## Responsabilidad

- Generar la URL OAuth para conectar una cuenta Google.
- Guardar tokens OAuth cifrados por usuario.
- Refrescar access tokens cuando expiran.
- Descargar archivos seleccionados desde Google Drive.
- Exportar archivos nativos de Google Workspace; la conversión elegida debe ser admitida por la ingesta.
- Enviar los archivos importados a `RagDocumentEmbeddingServices` para que entren al flujo normal de documentos, procesamiento y embeddings.
- Registrar el historial de importaciones y el estado por archivo.

## Puerto

```text
8017 -> 8000
```

## Variables principales

```text
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_DRIVE_ENABLED=false
DRIVE_DB_PASSWORD=blandskron-local-drive
GOOGLE_DRIVE_REDIRECT_URI=http://localhost:3000/documents
GOOGLE_TOKEN_ENCRYPTION_KEY=change-me-with-a-long-random-secret
RAG_DOCUMENT_BASE_URL=http://localhost:8003
```

En Docker, `RAG_DOCUMENT_BASE_URL` apunta a:

```text
http://rag-document-embedding-service:8000
```

## Endpoints

```text
GET  /api/v1/health
GET  /api/v1/health/db
POST /api/v1/google-drive/auth-url
POST /api/v1/google-drive/disconnect
POST /api/v1/google-drive/oauth/callback
GET  /api/v1/google-drive/connection
POST /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports/{import_id}
GET  /api/v1/google-drive/imports/{import_id}/files
```

## Flujo recomendado

1. La pestaña crea un verificador PKCE y envía su challenge S256 para obtener `authorization_url` y `state`.
2. El usuario conecta Google Drive.
3. El frontend valida el intento local y envía `code`, `state` y `code_verifier`; el servidor consume el intento antes del canje.
4. El frontend abre Google Picker con la misma aplicación OAuth.
5. El frontend envía los `file_id` seleccionados a `/google-drive/imports`.
6. El microservicio descarga o exporta cada archivo.
7. El microservicio sube cada archivo a `RagDocumentEmbeddingServices`.
8. Los documentos quedan disponibles en la biblioteca documental de Blandskron Documental.

## Tamaño del lote — DRIVE-005A

La API acepta entre 1 y 25 archivos por solicitud; fuera de ese rango responde 422. Si el límite configurado del servicio es menor, un lote que lo exceda responde 400 antes de consultar carpetas/conexiones, crear registros o llamar a proveedores. El lote se rechaza completo: no se recorta silenciosamente. Divide la selección en lotes admitidos. DRIVE-005 añade los límites y el protocolo de recuperación descritos a continuación.

## Importaciones acotadas y recuperables DRIVE-005

Despliega esquema, rol, Drive y frontend juntos, con escritores antiguos detenidos. `database-schema` incluye `drive/import_lifecycle.sql`; conserva dueños, ciphertext, documentos e historial y marca importaciones antiguas interrumpidas como REVIEW_REQUIRED. Ejecuta después `drive-db-role` y reconstruye el servicio/web. Las credenciales y datos personales no forman parte de las pruebas. El runtime sigue deshabilitado por defecto.

POST imports exige `operation_id` UUID canónico, `files` y, para vincular la selección web, `connection_version`. El schema prohíbe campos extra, IDs con rutas/query, archivos repetidos y nombres con separadores/controles; acota campos y metadata a 4 KiB, 32 elementos por colección y cuatro niveles. La metadata no puede sustituir identidad, source, folder/import ni campos Google reservados; el backend construye los campos de procedencia y Embedding conserva su propia autorización/estampado. El cuerpo completo tiene un máximo real de 64 KiB y una espera de lectura de 15 segundos antes de parsearlo.

La descarga usa streaming y un spool privado: hasta 1 MiB en memoria, después archivo temporal anónimo, cerrado también ante errores y revocación. Cuenta bytes reales sin depender de metadata o Content-Length: 20 MiB por archivo y 100 MiB por operación, incluyendo transferencias fallidas. Se rechazan tamaños falsos, respuestas parciales/redirecciones, contenido codificado y MIME inesperado. Solo se contactan endpoints configurados/soportados; no se siguen webViewLinks del proveedor. Las respuestas JSON de metadata/ingesta se limitan a 32 KiB y se validan sus tipos/identificadores. [Streaming HTTPX](https://www.python-httpx.org/quickstart/#streaming-responses) y [exportaciones oficiales de Google](https://developers.google.com/workspace/drive/api/guides/ref-export-formats).

El presupuesto de trabajo remoto es de 120 segundos por descarga y 600 por lote, comprobado entre lecturas, antes de cada fase y antes de iniciar solicitudes; cada espera de socket tiene además el timeout configurado (30 segundos por defecto). Una lectura ya iniciada puede consumir ese timeout antes de devolver control. No es una promesa de cancelación instantánea ni de tiempo exacto de respuesta HTTP, que también incluye transacciones SQL acotadas. Dos leases SQL globales, con un máximo de uno por dueño, limitan importaciones entre procesos/réplicas; el lease dura 15 minutos. Ningún lock/transacción se mantiene durante red. El spool se libera al terminar la carga, antes del procesamiento.

El diario crea el padre y sus archivos PENDING en una transacción. DOWNLOADING prueba que no se intentó cargar; UPLOADING se confirma antes del POST remoto. La carga usa `process=false`; su ID se guarda como UPLOADED antes de llamar al procesamiento documental. Un fallo o timeout de procesamiento conserva ese ID y produce PARTIAL con advertencia. La asociación de carpeta conserva el protocolo Library; un fallo tampoco repite la carga y mantiene el documento confirmado.

La misma clave, mismo payload y tenant devuelve el resultado guardado; un intento activo o una clave usada para otro payload/tenant devuelve 409. No se vuelve a descargar/cargar durante un replay. Una respuesta de carga perdida, JSON inválido o fallo ambiguo queda REVIEW_REQUIRED y bloquea otra carga del mismo archivo. Incluso con una clave nueva, un Google file ID ya cargado o pendiente de revisión para ese dueño no se vuelve a cargar. La identidad/permiso y las versiones de conexión/lease se comprueban antes de costes remotos. Reimportar revisiones de un mismo Google file ID no está implementado: requiere una política explícita de versiones, no eliminar los marcadores para forzar otra carga.

Los rechazos de autorización 401/403 de la ingesta ocurren antes de crear el documento y se registran FAILED, deteniendo las siguientes cargas del lote. Otras respuestas de carga no se interpretan como prueba de ausencia de documento. La web conserva la clave y el payload de un intento sin respuesta en sessionStorage, ligados a sesión/usuario/tenant. «Consultar importación pendiente» reenvía la misma operación, también tras recargar. Una operación fallida de forma conocida puede iniciar un intento nuevo; una incierta conserva la clave y requiere revisar el resultado. Cambiar de cuenta o conexión invalida las actualizaciones tardías. El historial y la cancelación se describen más abajo.

Consultar GET imports/{id} recupera un lease vencido del propio usuario. Un DOWNLOADING/PENDING interrumpido pasa a FAILED; UPLOADING pasa a REVIEW_REQUIRED; UPLOADED/COMPLETED conservan su ID. El padre recalcula contadores/estado y aumenta versión; un worker tardío pierde su permiso de escritura. No se repite ninguna carga en esa recuperación. FAILED cuenta fallos conocidos; processed_files cuenta documentos cuya creación se confirmó, aunque su procesamiento o asociación necesite revisión. REVIEW_REQUIRED identifica un resultado de creación desconocido, no un documento confirmado como perdido.

### Revisión y mantenimiento

Ante REVIEW_REQUIRED, localiza el documento por dueño y metadata.import_id/google_file_id mediante acceso autorizado. No infieras que no existe solo por un timeout o una consulta temprana: drena las solicitudes y revisa la ingesta en una ventana de mantenimiento. Conserva el documento encontrado y revisa procesamiento/asociación con los endpoints existentes de Embedding/Library. Resolver una ambigüedad necesita una disposición humana documentada; no hay botón ni tarea que borre esa evidencia o vuelva a cargarla automáticamente.

[maintain_imports.py](../../scripts/drive/maintain_imports.py) permite planificar recuperación y compactación de historial en un entorno de mantenimiento con `app` en PYTHONPATH. Exige `DRIVE_MAINTENANCE_DATABASE_URL` explícita con credenciales administrativas del entorno y no lee .env. No amplía privilegios del runtime. Usa secretos del despliegue, no argumentos ni archivos del repo:

```text
python /drive-checks/maintain_imports.py --plan /private/drive-imports-plan.json
# Revisar acciones, IDs, versiones y hashes fuera de Git; el plan no modifica datos.
python /drive-checks/maintain_imports.py --apply /private/drive-imports-plan.json
```

Procesa hasta 1000 entradas por plan. Recupera leases vencidos y compacta historial terminal sin advertencias pendientes, de más de 30 días. Conserva REVIEW_REQUIRED, archivos UPLOADED y advertencias sin resolver. PURGED elimina nombres/metadata del historial visible, pero conserva IDs/marcadores de fuente y operación para impedir duplicados; nunca elimina documentos, conexiones o credenciales. Aplicar verifica versión/hash bajo locks ordenados; cualquier cambio revierte el lote completo. Protege los planes como metadata privada y genera otro plan para el siguiente lote; la disposición de datos históricos no consiste en un borrado masivo.

## Formatos nativos de Google

```text
Google Docs   -> DOCX
Google Sheets -> PDF
Google Slides -> PDF
Google Drawing -> PDF
```

Docs se exporta a DOCX por defecto y admite PDF explícito. Sheets, Slides y Drawing se exportan a PDF. Los binarios admitidos coinciden con el contrato de ingesta: PDF, DOCX, TXT, Markdown, CSV, PNG, JPEG y TIFF. XLSX/PPTX binarios, carpetas, shortcuts y conversiones arbitrarias se rechazan antes de descargar contenido. La validación del contenido y extracción continúa perteneciendo a Embedding.

## Seguridad

- Requiere JWT de Blandskron Documental en todos los endpoints de usuario.
- Usa `drive.file` como scope recomendado.
- Cifra access token y refresh token antes de persistirlos.
- No expone archivos públicamente; todo entra al pipeline documental interno.

## Carpeta destino y resultados parciales

LIB-004 comprueba que `folder_id` pertenezca al usuario antes de consultar OAuth o descargar archivos. Una carpeta ajena o inexistente devuelve 404. El repositorio repite la comprobación al asociar y PostgreSQL exige que carpeta y asociación tengan el mismo propietario.

LIB-005 coordina el alta con los movimientos y retiradas de Library. Después de cargar el documento, toma el mismo bloqueo transaccional por usuario/documento, protege la referencia documental y bloquea la carpeta y sus ancestros desde la raíz. Inserta con conflicto idempotente y confirma. No mantiene bloqueos durante OAuth, descarga ni carga. Consulta el [protocolo de Library](../DocumentLibraryServices/README.md#escrituras-y-concurrencia) antes de cambiar este escritor y despliega ambos servicios juntos, sin escritores antiguos en paralelo.

Si el documento se importa pero la asociación falla, conserva el documento y su ID. El archivo queda `COMPLETED` con advertencia en `error_message` y `metadata.folder_association.status: FAILED`; la importación queda `PARTIAL`, con un mensaje genérico. `processed_files` incluye ese documento y `failed_files` cuenta los fallos de descarga o carga. Una asociación exitosa registra `metadata.folder_association.status: COMPLETED`. Sin carpeta seleccionada no se registra este resultado.

Ambas pantallas muestran incidencias y permiten consultar archivos/documentos guardados en el historial. Las fuentes completadas o inciertas conservan su marca y no admiten otra carga automática. Una asociación fallida se revisa sin volver a subir el documento.

## Pruebas del escritor de carpetas

Con PostgreSQL y `database-schema` iniciados, ejecuta desde la raíz:

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps drive-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps drive-tests ruff check --no-cache app tests
```

Las pruebas usan registros sintéticos con IDs únicos y limpieza explícita, PostgreSQL real y un proveedor simulado. No requieren OAuth ni descargan documentos. Cubren propiedad, inserción idempotente, espera real sobre el bloqueo compartido y fallos de asociación, incluido un resultado de carga sin ID documental. Esta suite también incluye identidad, OAuth, transporte, recuperación y páginas; sus proveedores son sintéticos.

## OAuth y credenciales DRIVE-004

Despliega esquema, servicio y frontend juntos. Detén escritores antiguos, respalda DB y claves en almacenamiento privado y ejecuta `database-schema` seguido de `drive-db-role`; reconstruye Drive y web. `scripts/database/run_all.sql` incorpora `drive/oauth_lifecycle.sql` de forma aditiva y repetible. Conserva ciphertext, dueño e historial: las conexiones anteriores quedan `LEGACY`, sin importación hasta revisión o reconexión. El nuevo runtime rechaza el callback anterior sin `state`/PKCE; GET auth-url devuelve 410 cuando está habilitado.

`POST /google-drive/auth-url` recibe `{code_challenge}` S256. Devuelve URL Google, `state` y redirect configurado; no acepta una redirección elegida por el cliente. El redirect debe ser `/documents` o `/applications/google-drive` sobre un origen CORS permitido y el mismo origen de la pestaña. Configúralo también en el cliente web de Google Cloud. El state aleatorio de 256 bits dura cinco minutos, se liga a usuario, huella, tenant, configuración y versión de conexión; solo se guarda su hash. Hay como máximo diez intentos pendientes por dueño, limpiados al iniciar otro flujo.

Ambas pantallas usan el mismo flujo: verificador aleatorio conservado en sessionStorage de la pestaña, comparación de state/sesión/ruta/caducidad y limpieza inmediata de parámetros OAuth también en errores. No hay tokens Google en DTO o almacenamiento del navegador; Picker obtiene un token efímero independiente. La sesión local conserva su identificador al recargar y lo cambia en un nuevo login; refresh conserva el cliente estable. El callback envía `{code,state,code_verifier,issuer?}`; el servidor consume el intento atómicamente antes de Google y exige S256. Los cuerpos de control se limitan a 16 KiB/15 s y las respuestas Drive llevan no-store/private. La pérdida de respuesta requiere empezar un intento nuevo, sin repetir ciegamente el canje.

La identidad Google se obtiene de `Drive about.user.permissionId` con el único scope `drive.file`; email es presentación. `GOOGLE_PICKER_APP_ID` debe coincidir con `VITE_GOOGLE_PICKER_APP_ID`, y el OAuth client ID público debe coincidir con `VITE_GOOGLE_CLIENT_ID`. Picker verifica aplicación y permissionId antes de abrirse y rechaza otra cuenta. No envía su token efímero al backend. [Metadatos Google con S256](https://accounts.google.com/.well-known/openid-configuration), [OAuth web](https://developers.google.com/identity/protocols/oauth2/web-server) y [Drive about](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get).

Las operaciones de credenciales usan una versión y un lease SQL de cinco minutos por dueño. Refresh, reconnect y revoke concurrentes devuelven 409; la versión/lease impide que una respuesta tardía reemplace otra conexión. No se mantienen transacciones sobre red. Un refresh fallido o ambiguo exige reautorización y conserva ciphertext. Un refresh omitido conserva el anterior; reconnect solo lo conserva para la misma cuenta previamente activa y con clave disponible. Una conexión heredada o de otro cliente requiere consentimiento offline nuevo. Se comprueba versión/estado antes de descargar y subir: una revocación posterior a esa comprobación no puede retirar una solicitud ya enviada.

`POST /google-drive/disconnect` recibe `{version}`. Revoca en Google antes de borrar las credenciales y conserva una fila DISCONNECTED con versión para impedir reutilizar una versión antigua. Un error de red, clave no disponible o integración deshabilitada devuelve 202/REVOKE_PENDING: no permite importar/reconectar y ofrece reintentar. No significa revocación confirmada. Un lease interrumpido se recupera al siguiente acceso tras vencer, con conflicto explícito; una renovación ambigua nunca se repite automáticamente. Para grants heredados de clave desconocida, conserva backup, retira acceso desde la cuenta Google y realiza una disposición manual revisada antes de retirar esa fila; no hay endpoint que finja revocación ni borre conexiones indiscriminadamente.

### Claves y rotación revisada

Configura secretos independientes mediante el gestor de secretos del despliegue; no en Git, argumentos CLI, logs o material de demo. `GOOGLE_TOKEN_KEY_ID=v1` etiqueta la clave activa `GOOGLE_TOKEN_ENCRYPTION_KEY`. `GOOGLE_TOKEN_PREVIOUS_KEYS` es un objeto JSON de hasta tres claves anteriores con identificadores diferentes. Cada ciphertext nuevo tiene formato `drive1.<key-id>.<Fernet>`. No se aceptan claves ausentes o prefijos de ejemplo; ningún fallback se activa. La pérdida de una clave no se resuelve generando otra con el mismo ID.

Para ciphertext antiguo sin envelope, `GOOGLE_TOKEN_LEGACY_KEY_ID` autoriza explícitamente una clave fuerte configurada en el keyring. Identificar primero qué clave lo generó. Grants cifrados con una constante pública/ejemplo o una clave perdida requieren revocación y consentimiento nuevo, no recifrado que los declare confiables. Rotar solo cambia cifrado/versión: no convierte LEGACY en ACTIVE ni inventa una cuenta Google.

En una ventana de mantenimiento, sin escritores antiguos, ejecuta [rotate_credentials.py](../../scripts/drive/rotate_credentials.py) en un entorno del servicio con `app` en PYTHONPATH y variables explícitas. El script no carga .env ni llama a Google:

```text
python /drive-checks/rotate_credentials.py --plan /private/drive-rotation.json
# Revisar fuera de Git: IDs de dueño, versiones, hashes y outcomes; nunca tokens.
python /drive-checks/rotate_credentials.py --apply /private/drive-rotation.json
```

El plan no modifica grants y marca claves desconocidas/leases como review_required. Aplicar procesa solo ready, verifica configuración, dueño/hash/versión y ausencia de lease bajo lock; cualquier cambio desde la revisión revierte toda la transacción. Admite hasta 1000 grants por ventana, no sobreescribe planes ni hace cambios parciales. Protege el archivo del plan como metadata privada. Verifica que no queden ciphertext con el ID anterior antes de retirar esa clave; conserva los backups según la política del operador. Nunca reutilices un key ID para otro secreto.

### Evidencia y alcance

Verificación local: 95 pruebas backend, 111 Node y 10 Chromium, npm ci/build, Ruff, pip-audit funcional sin avisos conocidos, Compose válido, provisión repetida y actualización/reinicio, y sonda Auth de tres roles aprobados. npm conserva cuatro alertas altas ya registradas en WEB-001; no se actualizaron dependencias web en este incremento. TestClient/httpx conserva su advertencia upstream.

La suite mantenida incluye state ausente/ajeno/vencido/replay, PKCE, tenant/configuración, consumo concurrente real, límites de intentos, refresh exitoso/fallido/ambiguo, lease vencido y respuesta tardía, reconnect sin refresh, desconexión/reintento y rotación revisada. El transporte HTTP de Google se simula con MockTransport; no se realizó OAuth real. Node cubre limpieza/correlación/coalescencia y cuenta/cliente Picker; Chromium cubre ambas páginas, callbacks rechazados, refresh de Auth y desconexión. Los comandos de pruebas abajo siguen vigentes. El diagnóstico siguiente conserva evidencia histórica; no representa el comportamiento nuevo.

## Operación DRIVE-002/003

`uvicorn app.main:create_app --factory --port 8017` construye la aplicación sin dotenv ni acceso DB/clave al importar. Son obligatorios DATABASE_URL PostgreSQL/psycopg y AUTH_JWT_PUBLIC_KEY_PATH absoluto; la clave RSA de al menos2048bits se lee sin caché al arrancar/verificar. PGPASSWORD mantiene la contraseña separada de la URL. Pool base1, máximo10 y timeout30s por conexión/pool/sentencia son efectivos; el pool crea conexiones bajo demanda. Fallar startup cierra la DB. Health público distingue liveness de /health/db (esquema/clave/helpers); respuestas de error no reflejan inputs, SQL ni excepciones de proveedores.

Drive está deshabilitado por defecto. Sin secretos Google puede arrancar, verificar readiness y consultar conexión/historial con identidad y permiso válidos. auth-url, callback e importaciones devuelven503 después de autenticar/autorizar; no construyen el cifrador ni llaman al proveedor. Para habilitarlo se exige GOOGLE_DRIVE_ENABLED=true, cliente/secreto y clave de cifrado independiente de al menos32caracteres, sin valores vacíos/de ejemplo. Los alias anteriores siguen admitidos, pero el proceso no lee archivos .env: Compose inyecta solo variables explícitas. CORS admite orígenes locales explícitos por defecto, [] lo desactiva y * se rechaza. Los endpoints Google son los HTTPS soportados y el scope es drive.file; ingesta admite su URL local de desarrollo o HTTPS.

**Mantener Drive deshabilitado por defecto.** Para una demo con Google, configurar un proyecto/cuentas de desarrollo y validar OAuth real expresamente; las pruebas automatizadas simulan el proveedor. No sustituir claves ni borrar grants heredados a ciegas.

### Identidad y permiso vigente

Se exige el contrato RS256 de Auth: user_id entero positivo canónico, exp/iat/jti/access y hash_password válidos. No se acepta dueño por sub/username/unknown. Un helper booleano privado comprueba cuenta activa y huella actual; otro evalúa el permiso actual desde PostgreSQL. Contraseña modificada o cuenta inactiva/eliminada:401; identidad válida sin acceso:403; dependencia SQL no disponible:503. Firma/claims inválidos se rechazan sin llamar al proveedor.

La conexión y el historial continúan siendo **globales del usuario**, sin convertirlos en recursos de tenant ni ampliar acceso a otros dueños. Para usarlos, un miembro activo de un tenant activo debe pertenecer en ese mismo tenant a un grupo con use_google_drive o *. Un administrador de tenant también necesita esa concesión explícita, coherente con la guarda UI existente; no basta un rol/permiso obsoleto del JWT. El superusuario se comprueba en auth_user actual, no en flags del cliente; una degradación pierde el bypass. Ingesta conserva por separado su autorización de upload y el estampado de tenant/propiedad.

Las comprobaciones usan transacciones cortas, terminadas antes de Google. El repositorio revalida al consultar/persistir y el caso de uso antes de exchange/userinfo/refresh/download/upload; la revocación durante una llamada impide el siguiente paso cuando vuelve a comprobarse. No se promete cancelar una petición de red ya enviada ni rollback de efectos del proveedor. Una revocación/fallo a mitad de importación se registra y se recupera según el diario; las cargas ambiguas requieren revisión.

### Permisos DB y despliegue

drive_runtime LOGIN sin membresías/superusuario/CREATE/RLS bypass puede seleccionar sus cuatro tablas, insertar y actualizar solo columnas de operación y eliminar intentos OAuth. No puede borrar conexiones/importaciones/archivos ni usar TRUNCATE, contraseñas, documentos ni carpetas. drive_helper_owner NOLOGIN conserva las columnas mínimas para cuatro funciones booleanas SECURITY DEFINER, con search_path fijo y EXECUTE privado: identidad, permiso, propiedad de carpeta y asociación. Esta última mantiene el advisory lock de Library, locks de documento/carpeta/ancestros y ON CONFLICT, además de exigir documento propio. El rol es una identidad del servicio, **no RLS por usuario**; los filtros del repositorio siguen delimitando al dueño.

[provision_role.sql](../../scripts/database/drive/provision_role.sql) es transaccional/repetible y [verify_role.sql](../../scripts/database/drive/verify_role.sql) rechaza privilegios inesperados, delegación, secuencias o ejecución de helpers ajenos. No repara silenciosamente concesiones extra. La contraseña pública de .env.example es solo desarrollo; usar una independiente al desplegar. La imagen usa UID10010 y targets separados runtime/test/audit, sin instalador ni pytest/Ruff en ejecución. La raíz es read-only, /tmp privado acotado, sin capabilities y con no-new-privileges; recursos y evidencia se describen abajo.

Para instalación nueva, desde raíz con configuración explícita:

```powershell
docker compose --env-file .env.example -f docker/docker-compose.yml up -d --build --wait google-drive-import-service
```

En una instalación existente, respaldar DB/configuración y detener el runtime antiguo. Mantener GOOGLE_DRIVE_ENABLED=false durante la actualización. Con esquema y Auth actualizados, ejecutar drive-db-role y reconstruir; no hay migración destructiva de conexiones/historial:

```powershell
docker compose -f docker/docker-compose.yml stop google-drive-import-service
docker compose -f docker/docker-compose.yml run --rm --no-deps drive-db-role
docker compose -f docker/docker-compose.yml up -d --build --wait google-drive-import-service
```

### Validación del paquete

Evidencia histórica de DRIVE-002/003 sobre proyecto/DB/claves sintéticos separados: 72 pruebas PostgreSQL/Linux, Ruff, provisión repetida, reinicio, login real del rol y SQLSTATE42501 para operaciones prohibidas. Incluyen modo deshabilitado, provider simulado habilitado, revocación durante red sin locks de Auth retenidos, aislamiento, privilegios inesperados, pool/rollback y pérdida de clave. La sonda [verify_auth_contract.py](../../scripts/drive/verify_auth_contract.py) corre dentro de Auth de desarrollo con marcador explícito: login/refresh de tres roles, permisos retirados, contraseña/inactividad/eliminación y limpieza de usuarios/tenant/budgets; no llama Google.

```powershell
docker compose -f docker/docker-compose.yml run --build --rm --no-deps drive-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps drive-tests ruff check --no-cache app tests /drive-checks
docker compose -f docker/docker-compose.yml run --build --rm --no-deps drive-audit
docker compose -f docker/docker-compose.yml config --quiet
```

La suite exige DRIVE_TEST_DATABASE_URL sintética y DRIVE_TEST_RUNTIME_PASSWORD, provistas por drive-tests. Fuera de Compose se puede ejecutar el subconjunto sin DB con pytest -m "not postgres"; no usar el runtime de producción para instalar herramientas. pip check y pip-audit del inventario funcional actualizado aprobaron sin avisos Python; el inventario se congela antes de instalar la herramienta y excluye pip, retirado del runtime. Esto no es un escaneo SO ni prueba de ausencia de vulnerabilidades. La advertencia TestClient/httpx se conserva; CI repite la suite y la sonda. BASELINE sigue siendo histórico, sin sobrescribir su evidencia ni atribuirle resultados de esta imagen.

## Historial y coordinación web

API y web se despliegan juntas: los GET de historial y archivos ahora devuelven `{items, next_cursor}`, no arrays. `limit` es 25 por defecto y admite 1..100. Importaciones: `?before=<next_cursor>`, orden descendente por created_at/import_id. Archivos: `?after=<next_cursor>`, orden ascendente por created_at/import_file_id. Cursor opaco acotado, ligado a dueño/tipo/padre; es una posición, no una autorización ni instantánea. Las consultas revalidan identidad/permiso y filtran dueño. Nuevas filas anteriores al cursor aparecen al actualizar; no se repiten las ya recorridas. Los índices se incorporan de forma aditiva en import_lifecycle.sql.

El historial funciona aun con Google deshabilitado. Solo presenta metadata de origen/carpeta y resultado documental/asociación, errores genéricos y nombres/tipos acotados; no reproduce metadata arbitraria heredada. PURGED conserva los marcadores pero oculta archivos. Consultar el detalle recupera leases vencidos. REVIEW_REQUIRED identifica un resultado incierto: inspeccionar los documentos guardados, sin reenvío automático.

Aplicaciones y Documentos comparten controlador y clave/payload de operación por sesión/usuario/tenant. Una sola operación local entre Picker/importación; límites 1..25 y sin IDs duplicados. Cancelar/cerrar/desmontar aborta la espera, descarta resultados y errores tardíos y conserva el intento pendiente: no garantiza cancelar el trabajo del servidor. «Consultar importación pendiente» reutiliza la clave original incluso tras recargar. El historial tiene diálogo nativo, Escape, foco restaurado y páginas con estados visibles; consultas canceladas no reemplazan la selección nueva.

Picker limita a 25 archivos, carga scripts en 15 s, autorización en 60 s y selección en cinco minutos; cada espera admite aborto y retira listeners/timers. Al cerrar o cancelar se destruye el selector y sus respuestas tardías se ignoran. Su token efímero solo va a Google para comprobar permissionId; no se guarda ni envía a la plataforma. [Límite oficial de selección](https://developers.google.com/workspace/drive/picker/reference/picker.pickerbuilder.setmaxitems) y [ciclo de vida Picker](https://developers.google.com/workspace/drive/picker/reference/picker.picker).

## Contenedor y evidencia de imagen

Runtime UID/GID 10010, sin pip/pytest/Ruff/pip-audit; raíz read-only, capabilities vacías y no-new-privileges. /tmp es tmpfs privado 0700 de 64 MiB, noexec/nosuid/nodev, suficiente para dos spools de 20 MiB con margen. Se limpia al cerrar cada archivo y al reiniciar; no contiene almacenamiento durable. Límites: 512 MiB RAM, una CPU, 128 procesos; Uvicorn 32 conexiones concurrentes y keep-alive cinco segundos. Los leases SQL siguen limitando a dos importaciones globales/una por dueño incluso con varias réplicas. La clave pública Auth se monta solo lectura; readiness comprueba DB/clave sin exponer valores.

[IMAGE_AUDIT.json](docs/IMAGE_AUDIT.json) conserva inventario/grafo de runtime, SO, ID de imagen, SHA del archivo y config escaneada, digest fijo Trivy y hashes de entradas de build. El script compara la config del archivo guardado con la escaneada, también con Docker containerd que identifica la imagen por índice OCI. Las herramientas reciben la imagen/archivo, nunca .env o documentos. El lector offline del tar usa el UID/GID del dueño del archivo, sin capabilities/red y con montaje exclusivo de ese archivo en solo lectura para acceder a archivos 0600 generados por docker save en Linux; la captura independiente de runtime conserva UID10010. La carpeta de evidencia se crea privada (0700), sin ampliar permisos del archivo. Sin supresiones. Las dos correcciones disponibles de zlib se aplicaron actualizando Debian; quedan 47 coincidencias HIGH en 11 CVE Debian sin fix indicado y cero críticos, seguimiento DRIVE-F01/PLAT-002. La auditoría funcional Python y la del SO son comprobaciones distintas.

Desde raíz, Node 24 y Docker, con un directorio de salida que aún no exista:

```sh
node scripts/drive/audit_image.mjs --image <imagen-runtime> --out <directorio-privado-nuevo>
docker compose -f docker/docker-compose.yml run --rm --no-deps -T drive-audit python /drive-checks/verify_runtime_dependencies.py < <directorio-privado-nuevo>/runtime.json
```

CI repite auditoría y grafo sobre su imagen y conserva JSON siete días. Falla con crítico, corrección disponible, hallazgo no OS o mismatch del artefacto; un fallo deja evidencia para revisión. El inventario histórico BASELINE no sustituye este escaneo. Reconstruir y reevaluar antes de publicación pública: no se declara ausencia de vulnerabilidades.

## Copia y restauración

Detener nuevos escritores Drive antes de una copia consistente: conservar backup PostgreSQL completo (tablas de Drive y Auth/Library/documentos relacionados), archivos documentales de ingesta y configuración privada de despliegue. Respaldar por separado keyring Google vigente/anterior con sus IDs, secreto OAuth y claves de Auth. Cifrar copias con acceso restringido y probar restauración fuera de producción. Un backup SQL sin la clave de cifrado no recupera grants; no generar otra clave con el mismo ID.

Restaurar primero en un entorno aislado con Google deshabilitado y sin escrituras a proveedores; restaurar DB/documentos/keyring de la misma copia, aplicar esquema/roles repetibles y comprobar readiness, permisos, propiedad y diario antes de habilitar acceso. Conservar marcadores de operaciones/fuentes y REVOKE_PENDING; una restauración no deshace uploads o revocaciones externos. Recuperar leases vencidos con el procedimiento de mantenimiento revisado; no convertir incertidumbre en FAILED ni reintentar cargas a ciegas. Para rollback parar nuevos escritores y restaurar la imagen compatible con el esquema aditivo; no ejecutar un escritor previo al diario sobre sus filas. Si se perdió una clave/grant, revisar y reautorizar explícitamente según la sección de rotación.

## Revisión final y alcance

DRIVE-006/007/008 agrupan contrato/web, contenedor y cierre en un incremento. Validación sintética: 165 pruebas PostgreSQL/HTTP, 123 Node y 16 escenarios Chromium del conjunto, npm ci/build, Ruff, Compose, pip check/audit, instalación nueva, actualización repetida, reinicio y sonda Auth real de tres roles. La suite cubre dos dueños, permisos/revocación, state/PKCE/refresh/revoke, formatos/bytes/timeouts, fallos de upload/asociación, replay/leases, retención y privacidad de páginas. Navegador usa APIs simuladas; no es OAuth real. La evidencia de ejecución y estado de integración se registra en ROADMAP.

Se conserva código de mantenimiento, esquema, pruebas y BASELINE/HISTORY necesarios para operación o trazabilidad; docs solo contiene documentación/JSON, scripts mantenidos viven fuera. La revisión no habilita Google ni usa grants/documentos personales. El cierre funcional no cierra PLAT-001, WEB-001, PLAT-002 o DEMO-001; cuatro alertas npm conocidas y DRIVE-F01 siguen explícitos.
