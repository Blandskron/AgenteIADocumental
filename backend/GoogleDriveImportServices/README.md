# GoogleDriveImportServices

Microservicio responsable de conectar Google Drive con la biblioteca documental de Blandskron Documental.

**Estado:** DRIVE-001/002/003 integrados. DRIVE-004 en revisión: OAuth PKCE, credenciales versionadas y callbacks compartidos. Importación acotada/recuperable, controlador web completo e imagen conservan sus tarjetas; el servicio no está cerrado. [Tablero](../../ROADMAP.md#googledriveimportservices), [guía para agentes](AGENTS.md) y [línea base histórica](docs/BASELINE.json).

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

## Formatos nativos de Google

```text
Google Docs   -> DOCX
Google Sheets -> XLSX
Google Slides -> PPTX
Google Drawing -> PDF
```

Estos son los formatos que solicita el cliente actual, no una garantía de procesamiento. Embedding admite PDF/DOCX y otros formatos de su contrato, pero no XLSX/PPTX. DRIVE-005 debe elegir una conversión compatible para Sheets/Slides o rechazarlos explícitamente antes de descargar; no basta con que Google complete la exportación.

## Seguridad

- Requiere JWT de Blandskron Documental en todos los endpoints de usuario.
- Usa `drive.file` como scope recomendado.
- Cifra access token y refresh token antes de persistirlos.
- No expone archivos públicamente; todo entra al pipeline documental interno.

## Carpeta destino y resultados parciales

LIB-004 comprueba que `folder_id` pertenezca al usuario antes de consultar OAuth o descargar archivos. Una carpeta ajena o inexistente devuelve 404. El repositorio repite la comprobación al asociar y PostgreSQL exige que carpeta y asociación tengan el mismo propietario.

LIB-005 coordina el alta con los movimientos y retiradas de Library. Después de cargar el documento, toma el mismo bloqueo transaccional por usuario/documento, protege la referencia documental y bloquea la carpeta y sus ancestros desde la raíz. Inserta con conflicto idempotente y confirma. No mantiene bloqueos durante OAuth, descarga ni carga. Consulta el [protocolo de Library](../DocumentLibraryServices/README.md#escrituras-y-concurrencia) antes de cambiar este escritor y despliega ambos servicios juntos, sin escritores antiguos en paralelo.

Si el documento se importa pero la asociación falla, conserva el documento y su ID. El archivo queda `COMPLETED` con advertencia en `error_message` y `metadata.folder_association.status: FAILED`; la importación queda `PARTIAL`, con un mensaje genérico. `processed_files` incluye ese documento y `failed_files` cuenta los fallos de descarga o carga. Una asociación exitosa registra `metadata.folder_association.status: COMPLETED`. Sin carpeta seleccionada no se registra este resultado.

DocumentSearchPage muestra el mensaje de la importación parcial después de refrescar la biblioteca. Revisa los documentos antes de reintentar: repetir la importación podría crear otro documento. No se reintenta automáticamente una carga ya completada.

## Pruebas del escritor de carpetas

Con PostgreSQL y `database-schema` iniciados, ejecuta desde la raíz:

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps drive-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps drive-tests ruff check --no-cache app tests
```

Las pruebas usan registros sintéticos con IDs únicos y limpieza explícita, PostgreSQL real y un proveedor simulado. No requieren OAuth ni descargan documentos. Cubren propiedad, inserción idempotente, espera real sobre el bloqueo compartido y fallos de asociación, incluido un resultado de carga sin ID documental. Este alcance coordina el escritor con Library; no constituye el cierre de modernización de GoogleDriveImportServices.

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

**Mantener Drive deshabilitado para publicación hasta completar DRIVE-005/006.** DRIVE-004 sustituye el callback code-only y añade el ciclo de credenciales descrito abajo. Descarga, recuperación de ingesta y coordinación web completa siguen pendientes. No sustituir claves ni borrar grants heredados a ciegas.

### Identidad y permiso vigente

Se exige el contrato RS256 de Auth: user_id entero positivo canónico, exp/iat/jti/access y hash_password válidos. No se acepta dueño por sub/username/unknown. Un helper booleano privado comprueba cuenta activa y huella actual; otro evalúa el permiso actual desde PostgreSQL. Contraseña modificada o cuenta inactiva/eliminada:401; identidad válida sin acceso:403; dependencia SQL no disponible:503. Firma/claims inválidos se rechazan sin llamar al proveedor.

La conexión y el historial continúan siendo **globales del usuario**, sin convertirlos en recursos de tenant ni ampliar acceso a otros dueños. Para usarlos, un miembro activo de un tenant activo debe pertenecer en ese mismo tenant a un grupo con use_google_drive o *. Un administrador de tenant también necesita esa concesión explícita, coherente con la guarda UI existente; no basta un rol/permiso obsoleto del JWT. El superusuario se comprueba en auth_user actual, no en flags del cliente; una degradación pierde el bypass. Ingesta conserva por separado su autorización de upload y el estampado de tenant/propiedad.

Las comprobaciones usan transacciones cortas, terminadas antes de Google. El repositorio revalida al consultar/persistir y el caso de uso antes de exchange/userinfo/refresh/download/upload; la revocación durante una llamada impide el siguiente paso cuando vuelve a comprobarse. No se promete cancelar una petición de red ya enviada ni rollback de efectos del proveedor. Una revocación/fallo a mitad de importación puede requerir la recuperación aún pendiente en DRIVE-005.

### Permisos DB y despliegue

drive_runtime LOGIN sin membresías/superusuario/CREATE/RLS bypass puede seleccionar sus tres tablas, insertar y actualizar solo columnas de operación. No tiene DELETE, TRUNCATE, contraseñas, documentos ni carpetas. drive_helper_owner NOLOGIN conserva las columnas mínimas para cuatro funciones booleanas SECURITY DEFINER, con search_path fijo y EXECUTE privado: identidad, permiso, propiedad de carpeta y asociación. Esta última mantiene el advisory lock de Library, locks de documento/carpeta/ancestros y ON CONFLICT, además de exigir documento propio. El rol es una identidad del servicio, **no RLS por usuario**; los filtros del repositorio siguen delimitando al dueño.

[provision_role.sql](../../scripts/database/drive/provision_role.sql) es transaccional/repetible y [verify_role.sql](../../scripts/database/drive/verify_role.sql) rechaza privilegios inesperados, delegación, secuencias o ejecución de helpers ajenos. No repara silenciosamente concesiones extra. La contraseña pública de .env.example es solo desarrollo; usar una independiente al desplegar. La imagen usa UID10010 y targets separados runtime/test/audit, sin instalador ni pytest/Ruff en ejecución. El hardening read-only/recursos y escaneo SO/vendorizados siguen en DRIVE-007.

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

## Diagnóstico histórico DRIVE-001

Esta sección y BASELINE describen la revisión histórica anterior a DRIVE-002/003, no las garantías del runtime actual. La operación vigente y sus límites se explican a continuación.

Revisión de `e20052ba1d1b399091ddda1ed1ebee762d2289f4`, el 8 de noviembre de 2026. Se leyeron los 39 archivos rastreados del servicio y se contrastaron los consumidores web, Auth, Library, ingesta, Compose y SQL. Auditoría estática con revisiones independientes y validación del padre: tres hallazgos medios y uno bajo condicionado. No se usaron OAuth, claves ni documentos reales ni se intentó agotar memoria. No se cambió el runtime en este incremento.

| Frontera | Comportamiento comprobado | Mejora y aceptación |
| --- | --- | --- |
| Identidad | JWT firmado y access, sin cuenta activa/huella vigente; dueño con fallback. Firma, expiración y consultas por dueño sí existen. | DRIVE-003: identidad canónica, revocación y dependencia de Auth saneada antes de Google. No se demostró falsificación de JWT ni impersonación por el fallback. |
| OAuth | `auth_url` devuelve state como JSON base64; callback y ambas páginas envían solo code, sin intento almacenado/consumido. La navegación a la página real hace que la web aporte el JWT. | DRIVE-004: intento ligado a identidad/navegador, state aleatorio corto y de un uso antes del canje, PKCE validado para el flujo elegido, pruebas de ausencia/cruce/caducidad/replay. No se demostró exposición del Drive original de la víctima. |
| Cifrado/renovación | Fernet cifra tokens; clave vacía activa constante pública. Refresh conserva token omitido, pero reconnect puede reemplazarlo por null; falta versión frente a refresh concurrente. | DRIVE-004: configuración que falla cerrado, clave independiente/versionada, rotación/reautorización y desconexión revisadas. El fallo de confidencialidad exige además leer ciphertext de una instalación con fallback, no un acceso API anónimo. |
| Descarga | `Client.get` y `response.content` cargan todo; tamaño de metadata no se limita. El máximo 20 MiB de ingesta llega después. | DRIVE-005: cota de bytes reales durante streaming, presupuesto total, exportaciones, spool/cleanup y concurrencia. Timeout de 90 s y lote de 25 no sustituyen una cota de memoria. |
| Persistencia | Import, archivos y finalización confirman por separado; sin clave de operación, lease o reconciliación. Fallos fuera del try por archivo pueden conservar RUNNING. | DRIVE-005/006: estados y recuperación explícitos, operación idempotente y tratamiento de upload ambiguo que no duplique documentos. No confundir ON CONFLICT de carpeta con idempotencia de importación. |
| Historial/web | Lista limitada sin cursor/desempate; archivos sin paginación. Cliente cambia durante refresh; callbacks/Picker/importaciones no tienen la coordinación estable de Profile/Export. | DRIVE-006: contrato paginado y cliente con generación/abort por cuenta/tenant/desmontaje, cancelación/doble envío/reintento, errores y accesibilidad; Node/Chromium. |
| Permisos/tenant | Estado Drive pertenece al usuario; no hay tenant en sus tablas ni validación backend de use_google_drive. Ingesta aplica por separado permiso y metadata de identidad. | DRIVE-003: acordar explícitamente permiso y alcance global/tenant, revisar todos los consumidores y cambios de tenant. La guarda de UI sola no prueba un contrato backend ni otro hallazgo independiente. |
| Runtime | main crea configuración/DB globales; dotenv relativo, CORS *, pool/timeouts declarados sin consumir y health estático. Compose importa .env global y usa postgres; imagen root con pytest/Ruff en runtime y base sin digest. | DRIVE-002/003/007: factory, modo opcional, readiness y errores saneados, configuración explícita, rol mínimo y contenedor acotado/auditado. La publicación Compose es loopback; no se presupone exposición a Internet. |

El repositorio usa parámetros SQL, filtros propios de conexión/importación y comprobación del padre antes de listar archivos. Las asociaciones conservan propiedad y locks Library. No se encontró un camino probado de SQL injection, SSRF a hosts arbitrarios, ejecución por filename o secreto real incrustado. Las bases remotas son configuración del operador y HTTPX no habilita redirects. `str(exc)` y el texto parcial de errores de upload requieren saneamiento, sin afirmar filtración de credenciales demostrada.

### Decisiones y orden de trabajo

Mantendremos la estructura del servicio y corregiremos sus fronteras con pruebas. Una cola no arreglaría por sí sola identidad, callback ni cifrado; se reconsiderará si los requisitos o las mediciones exigen reanudación/capacidad adicional. No se sostendrán locks de identidad o carpeta durante llamadas Google lentas. No se migrarán ni eliminarán tokens, propietarios, documentos o historial sin un inventario y una estrategia revisados.

Los cuatro paquetes propuestos son runtime/identidad/rol (DRIVE-002/003), OAuth/cifrado y callbacks (DRIVE-004), importaciones y web (DRIVE-005/006), y artefacto/cierre (DRIVE-007/008). Son propuestas para reducir PRs; cada criterio sigue siendo obligatorio y el tamaño puede exigir separar un paquete. Google Drive seguirá opcional y las pruebas usarán transportes/proveedores simulados por defecto.

### Evidencia y límites

En Docker Linux/Python 3.12.16 se ejecutaron las nueve pruebas existentes, Ruff, `pip check`, OpenAPI (siete paths/ocho operaciones) y Compose config. Proyecto dedicado con DB nueva; sin arrancar la integración Google ni montar documentos. Los conteos posteriores de documentos, carpetas, asociaciones, conexiones e importaciones fueron cero. El inventario de dependencias instalado y su auditoría separada se registran en BASELINE; no es un escaneo SO ni una prueba de explotabilidad. Las herramientas de auditoría se instalaron después de congelar el inventario, en un contenedor efímero sin credenciales.

La auditoría no está limpia: OSV devolvió 83 registros, 43 IDs de aviso distintos y siete paquetes; son registros con duplicados, no 83 vulnerabilidades únicas. PyPI devolvió 12 registros/10 IDs atribuidos a un solo paquete, incluyendo avisos que la fuente de Starlette identifica como propios de Starlette. Se conservan ambos resultados sin corregirlos silenciosamente; DRIVE-002 debe verificar atribución y actualizar un conjunto compatible, y DRIVE-007 auditar su imagen final. Se contrastaron el [aviso upstream de cryptography](https://github.com/pyca/cryptography/security/advisories/GHSA-p423-j2cm-9vmq) y los [avisos upstream de Starlette](https://github.com/Kludex/starlette/security/advisories). Ningún conteo prueba por sí solo que una ruta de este servicio sea explotable.

La guía agents-first se contrastó con el [README del framework](https://github.com/Blandskron/agents-first-repo-docs/blob/main/README.md), versión declarada 3.2.0, consultado el 8 de noviembre: entrada humana en README, instrucciones locales en AGENTS, tareas en ROADMAP y evidencia machine-readable sin duplicar código en docs. El portal no estuvo accesible en la consulta; se leyó su fuente conectada en GitHub.

Google exige cotejar state antes de procesar la respuesta; la [guía OAuth web](https://developers.google.com/identity/protocols/oauth2/web-server) y [buenas prácticas](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) respaldan esa frontera y el tratamiento de tokens. La [BCP OAuth RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) orienta PKCE/CSRF y el enlace al navegador; no asumimos compatibilidad de un SDK sin verificar el flujo concreto. La [guía de descarga/exportación Drive](https://developers.google.com/workspace/drive/api/guides/manage-downloads) distingue blobs y exports: su límite de exportación no reemplaza la cota local de la aplicación.
