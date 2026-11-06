# DocumentLibraryServices

Organiza documentos en carpetas personales, favoritos y una vista de documentos actualizados recientemente. Usa FastAPI, SQLAlchemy y el PostgreSQL compartido. El puerto local de Compose es `8006`.

LIB-001 estableció el diagnóstico y el plan. LIB-002 incorporó configuración y pruebas; LIB-003 unifica permisos; LIB-004 refuerza integridad; LIB-005 serializa escrituras; LIB-006 limita entradas; LIB-007 pagina los listados y coordina sus consumidores web. Los privilegios de ejecución y el cierre siguen en LIB-008. El [tablero](../../ROADMAP.md#documentlibraryservices) es la fuente de tareas y [AGENTS.md](AGENTS.md) indica cómo intervenir el servicio.

## Recorrido y responsabilidades

```text
DocumentSearchPage / ChatPage
  → useDocumentLibrary → document-library.api.js
  → rutas → ManageLibrary → LibraryRepositoryPg → PostgreSQL
```

Modifica `document_folders`, `document_folder_items` y `document_favorites`. Consulta `documents`, `document_assignments` y los IDs de `document_embeddings` para contar fragmentos. No abre archivos, no extrae texto ni llama a un proveedor de IA.

Eliminar una carpeta elimina sus descendientes y asociaciones mediante cascadas de PostgreSQL. Conserva documentos, favoritos y archivos. Retirar una asociación o un favorito tampoco borra el documento. La eliminación documental corresponde a DocumentAccessServices.

`recent` devuelve documentos `PROCESSED` ordenados por `documents.updated_at`. Representa documentos actualizados, no un historial de visitas del usuario.

## Contrato HTTP actual

Las rutas de negocio requieren `Authorization: Bearer <token>` con firma RSA válida, `token_type: access`, `user_id` entero positivo y `exp` entero vigente. Se rechazan identidades ausentes, booleanas, de texto, cero o negativas, y vencimientos ausentes o de otro tipo. `sub`, `username` y `unknown` no sustituyen a `user_id`. Un token inválido devuelve HTTP 401 con `WWW-Authenticate: Bearer` antes del caso de uso.

Los dos healthchecks son públicos. Carpetas, contenido, recientes y favoritos devuelven páginas `{items, limit, offset, has_more}`. Admiten `limit` de 1 a 100, por defecto 50, y `offset` de 0 a 1000000, por defecto 0. `has_more` se calcula con una fila adicional, sin publicar un total global.

| Método y ruta bajo `/api/v1` | Respuesta actual |
| --- | --- |
| `GET /health`, `GET /health/db` | `{"status":"ok"}`. `/health` comprueba vida; `/health/db` valida dependencias y devuelve 503 si fallan. |
| `GET /folders?parent_folder_id=...` | Carpetas propias en ese nivel, con conteo de documentos visibles. Un padre ajeno o inexistente devuelve 404. Sin parámetro devuelve raíces. |
| `POST /folders` | Carpeta creada, HTTP 201. |
| `PATCH /folders/{folder_id}` | Carpeta actualizada. Cambia nombre y metadatos, no padre. |
| `DELETE /folders/{folder_id}` | `{"deleted":true/false}`. |
| `GET /folders/{folder_id}/documents` | Documentos visibles asociados por el usuario a su carpeta. Carpeta ajena o inexistente devuelve 404. |
| `POST /folders/{folder_id}/documents/{document_id}` | `{"deleted":true/false}` aunque agrega una asociación. |
| `DELETE /folders/{folder_id}/documents/{document_id}` | `{"deleted":true/false}`. |
| `PATCH /library/documents/{document_id}/folder` | `{"success":true}` o HTTP 404. `folder_id: null` retira las asociaciones personales. |
| `GET /library/recent?limit=50&offset=0` | Página de documentos actualizados recientemente según el filtro de acceso actual. |
| `GET /library/favorites` | Favoritos según el filtro de acceso actual. |
| `POST /library/favorites/{document_id}` | `{"count":1/0}`. El cero puede indicar falta de acceso. |
| `DELETE /library/favorites/{document_id}` | `{"count":1/0}`. |
| `POST /library/markers` | Recibe `{"document_ids":[...]}` con 1 a 100 IDs. Devuelve arreglo de `{document_id,is_favorite}` solo para documentos visibles; omite ajenos, revocados e inexistentes y elimina duplicados. No modifica datos. |

Hay trece operaciones de negocio y dos healthchecks. La respuesta documental contiene ID, nombre, MIME, estado, cantidad de fragmentos, fecha de actualización e `is_favorite` del usuario. La carpeta incluye ID, nombre, padre, propietario, metadatos, cantidad de documentos visibles y fechas. No se publican rutas de almacenamiento ni vectores.

## Paginación y alcance de navegación

Las carpetas se ordenan por nombre e ID ascendentes; los documentos recientes por actualización e ID descendentes; los favoritos por fecha de alta e ID descendentes; el contenido por fecha de asociación e ID descendentes. El desempate único sigue las [reglas de LIMIT/OFFSET de PostgreSQL](https://www.postgresql.org/docs/16/queries-limit.html). Los filtros de acceso se aplican antes del límite, offset y conteo; cambiar de página no concede acceso.

Cada petición ve los datos actuales, sin una instantánea compartida entre páginas. Altas, borrados, revocaciones y cambios de orden pueden desplazar filas entre peticiones. El controlador deduplica por ID y avanza por el número de filas recibidas, no por el de IDs únicos. Usa **Actualizar biblioteca** para volver a las primeras páginas; también se reinician después de crear, mover o cambiar favoritos. No se promete un recorrido sin omisiones mientras otros clientes escriben.

Fragmentos y favoritos se agregan por lote para los documentos de la página, sin consultas por documento. Una raíz requiere una consulta; recientes y favoritos, tres; contenido, cuatro contando la comprobación de propiedad. Los conteos de carpeta representan todos sus documentos visibles, aunque solo se hayan cargado algunas páginas. Las pruebas miden número de consultas, no latencia ni rendimiento a gran escala.

La interfaz permite cargar más carpetas raíz, contenido de la carpeta seleccionada, favoritos y documentos actualizados recientemente. El selector de movimiento también permite cargar más raíces. Los contadores indican registros cargados y no calculan almacenamiento a partir de fragmentos. Las etiquetas de carpeta aparecen únicamente dentro de la carpeta seleccionada; se retiró el mapa global acumulado y sus consultas por carpeta.

La API admite crear y listar subcarpetas con `parent_folder_id`, incluso con paginación y control de propietario. La interfaz web actual crea y navega raíces y su contenido; no ofrece árbol, breadcrumbs, creación de subcarpetas ni movimiento de carpetas. No interpreta una raíz como un listado recursivo de sus descendientes.

El frontend y Library deben desplegarse juntos: los arreglos anteriores se sustituyen por páginas. El adaptador rechaza un contrato incompatible con un error visible. No hay migración ni variables nuevas en LIB-007. La búsqueda general conserva su contrato propio de DocumentSearchServices y su límite actual; esta entrega no agrega paginación a esa búsqueda.

Crear recibe `name`, `parent_folder_id` opcional y `metadata`. Actualizar recibe al menos `name` o `metadata`; omitir un campo lo conserva y enviar `null` se rechaza. Mover exige `folder_id` explícito: un ID selecciona destino y `null` retira las asociaciones personales. Un cuerpo vacío nunca se interpreta como mover a ninguno. Los tres cuerpos rechazan campos desconocidos.

## Límites y errores de entrada

| Entrada | Contrato LIB-006 |
| --- | --- |
| IDs en ruta, consulta o cuerpo | Texto de 1 a 128 caracteres, Unicode válido, no compuesto solo de espacios ni con controles ASCII o DEL. No se exige UUID ni se recortan los IDs. |
| Nombre | Texto Unicode válido de 1 a 200 caracteres después de `strip`. Se rechazan controles ASCII y DEL incluso antes de recortar; se preservan mayúsculas y espacios interiores. |
| Metadatos | Objeto JSON, máximo 16384 bytes UTF-8 al serializar sin espacios con `ensure_ascii=False`, profundidad máxima 16 desde raíz 0. Claves y valores cuentan para la profundidad. Sin NUL, Unicode inválido ni números no finitos. `{}` vacía los metadatos. |
| Cuerpo HTTP | Máximo 65536 bytes reales, incluidos espacios y fragmentos del stream. No depende de `Content-Length`; se comprueba antes de decodificar JSON y ejecutar el caso de uso. Aplica también a cuerpos de GET y DELETE. |
| Páginas | `limit` entre 1 y 100, por defecto 50; `offset` de 0 a 1000000. Los valores fuera de rango devuelven 422 privado. |

Estos límites son parte del contrato, sin variables nuevas de entorno ni migración. No se recortan nombres o metadatos históricos al leerlos. Los consumidores actuales envían un destino explícito al mover y nombre recortado al crear. El adaptador y el lector compartido de errores admiten `detail` de texto o una lista de errores.

| HTTP | Significado |
| --- | --- |
| 400 | Fallo de decodificación del cuerpo o validación de una operación de aplicación; mensajes constantes. |
| 401 | JWT ausente o inválido, con `WWW-Authenticate: Bearer`. |
| 404 | Recurso ajeno o inexistente en las operaciones que usan 404. Se conservan los booleanos y contadores de las otras operaciones. |
| 409 | Nombre de carpeta repetido al mismo nivel; rollback antes de responder. |
| 413 | Cuerpo mayor a 65536 bytes, incluso sin autenticación: se comprueba antes del router. CORS se conserva para orígenes permitidos. |
| 422 | JSON mal formado o incumplimiento del esquema: nombre, ID, metadatos, tipo, campos desconocidos o cambios ausentes. |
| 500 | Error interno SQL o de aplicación; respuesta genérica. No se convierte un fallo en un booleano o contador exitoso. |

Los errores 422 conservan solo `loc`, `msg` y `type`; omiten `input`, `ctx` y el cuerpo. Las ubicaciones desconocidas se sustituyen por `field` y el mensaje es constante, de modo que tampoco se reflejan claves enviadas por el cliente. Esto adapta el [manejo de RequestValidationError de FastAPI](https://fastapi.tiangolo.com/tutorial/handling-errors/) al contrato de privacidad del servicio. Los errores SQL no publican consultas ni parámetros; las escrituras revierten antes de propagar errores y recuperan la sesión. OpenAPI documenta las restricciones y respuestas comunes.

## Lectura y organización personal

Recientes, favoritos, contenido de carpeta, conteos y comprobaciones de alta o movimiento aplican la misma política documental que DocumentSearchServices y DocumentAccessServices.

| Concesión | Alcance |
| --- | --- |
| Propietario | La columna `owner_user_id` prevalece. Los metadatos sirven de respaldo únicamente si falta la columna. |
| Asignación | Destinatario o asignador pueden leer mientras el estado no sea `CANCELLED` ni `EXPIRED`. Varias asignaciones no duplican filas ni conteos. |
| Administrador de tenant | Lee documentos del tenant declarado en sus membresías del JWT. La columna `tenant_id` prevalece sobre metadatos históricos. |
| Grupo | Requiere coincidencia de grupo y membresía en el tenant efectivo del documento. Los documentos sin tenant conservan acceso por grupo para compatibilidad. |
| Superadministrador | Puede leer documentos, pero conserva únicamente su propia organización de carpetas y favoritos. |

Las asignaciones se consultan en PostgreSQL en cada operación. Los roles, grupos y membresías se toman del token verificado y mantienen la vigencia de ese token. La revocación de una asignación quita esa concesión en la siguiente consulta; otros permisos independientes pueden seguir concediendo lectura.

Guardar un favorito o una asociación no concede acceso. Los listados y los conteos ocultan documentos inaccesibles, aunque sus marcadores sigan almacenados. Las carpetas vacías siguen apareciendo con cero y el frontend usa `document_count`, conservando el cero sin sustituirlo por un valor histórico de metadatos.

Las carpetas siguen siendo privadas por `user_id`, incluso para administradores de documentos. Leer una carpeta comprueba tanto al propietario de la carpeta como al de sus asociaciones. Retirar una asociación exige carpeta propia; retirar un favorito o una asociación propia permite limpiar marcadores revocados sin devolver información del documento. Agregar o mover requiere lectura documental actual y carpeta destino propia; el movimiento a `null` también comprueba lectura. Los resultados booleanos y contadores de escritura se mantienen hasta la revisión de contrato de las siguientes tarjetas.

## Escrituras y concurrencia

Agregar a favoritos o a una carpeta es idempotente: una repetición autorizada devuelve éxito y conserva un único marcador, sin cambiar su fecha original. Se usa `INSERT ... ON CONFLICT DO NOTHING` sobre las claves existentes, según el [contrato de PostgreSQL](https://www.postgresql.org/docs/16/sql-insert.html). Retirar devuelve si esta operación eliminó un marcador; repetir una retirada devuelve cero o falso. Borrar una carpeta también informa si esta operación la eliminó.

Agregar permite varias carpetas propias. Mover reemplaza todas las asociaciones del usuario por un destino o ninguno, en una sola transacción. Dos movimientos simultáneos quedan ordenados: al terminar conserva el destino del último movimiento que obtuvo el bloqueo, nunca la unión accidental de ambos. Un alta posterior a un movimiento puede agregar otra carpeta. Otros usuarios conservan sus asociaciones.

Library y Google Drive usan el mismo protocolo bajo el aislamiento PostgreSQL predeterminado `READ COMMITTED`:

1. Bloqueo transaccional `pg_advisory_xact_lock(hashtextextended('blandskron.library.document:' || owner || ':' || document, 0))`. El propietario es el ID de usuario canónico como texto. La clave identifica la organización de ese usuario y documento; una posible colisión del hash solo añade espera.
2. Referencia documental con `FOR KEY SHARE`; las altas y movimientos consultan además el filtro de acceso actual. Las retiradas permiten limpiar marcadores revocados y no devuelven información documental.
3. Carpeta propia y sus ancestros con `FOR KEY SHARE`, en orden raíz a destino. Esto coordina las escrituras con borrados en cascada de cualquier ancestro.
4. Inserción o retirada de marcadores y commit. Un fallo revierte toda la operación; las salidas denegadas también terminan la transacción y liberan los bloqueos.

Los [bloqueos transaccionales de PostgreSQL](https://www.postgresql.org/docs/16/explicit-locking.html) se liberan al hacer commit o rollback. No se mantiene una transacción abierta durante descargas, carga documental o llamadas al proveedor. Usuarios o documentos distintos pueden organizarse en paralelo; el bloqueo de referencia solo coordina el borrado del documento compartido. Una escritura que espera un borrado vuelve a comprobar la existencia antes de modificar marcadores.

El protocolo es cooperativo: cualquier nuevo escritor directo de asociaciones debe respetar la misma clave y orden. Las claves foráneas siguen protegiendo la integridad SQL. No cambia la vigencia de claims del JWT ni convierte un marcador en permiso. Al desplegar LIB-005, actualiza Library y Google Drive juntos y evita mantener escritores antiguos en paralelo. No requiere migración adicional sobre LIB-004.

LIB-008 debe resolver el privilegio requerido por `SELECT FOR KEY SHARE` mediante un mecanismo acotado, conservando los documentos sin permisos generales de modificación para el rol de Library. No basta con sustituir la conexión administrativa por un rol con solo `SELECT` y asumir que estas escrituras seguirán funcionando.

## Consumidores que deben revisarse juntos

- El [adaptador](../../frontend/src/features/document-library/api/document-library.api.js) valida páginas, conserva `has_more`, codifica IDs de ruta y falla ante arreglos anteriores.
- El [hook](../../frontend/src/features/document-library/hooks/useDocumentLibrary.js) conecta React con un [controlador por cliente](../../frontend/src/features/document-library/library-controller.js). Versiona peticiones para descartar páginas tardías tras refrescar, cerrar o cambiar de carpeta y desmontar. Un cliente nuevo empieza con estado vacío. La búsqueda usa la misma separación por cliente y descarte de resultados tardíos.
- [DocumentSearchPage](../../frontend/src/pages/DocumentSearchPage/DocumentSearchPage.jsx) consulta marcadores por lote para resultados visibles. Antes de alternar un favorito comprueba su estado real, incluso si está fuera de la página cargada; un alta con `count=0` muestra error. Los errores se conservan después de refrescar y aparecen también dentro de los diálogos.
- [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) pasaba datos de biblioteca a ChatMessages, que no los utilizaba. LIB-007 retira esos props y las peticiones sin consumidor; el chat no presenta listas parciales ni un árbol de carpetas inexistente.
- [GoogleDriveImportServices](../GoogleDriveImportServices/README.md) inserta directamente en `document_folder_items`. LIB-004 comprueba la carpeta propia antes de consultar al proveedor y vuelve a comprobarla al asociar. Una asociación fallida conserva el documento importado, marca la importación `PARTIAL` y muestra una advertencia en DocumentSearchPage. Las pruebas usan un proveedor simulado, sin OAuth.

## Integridad y migración de carpetas

La [migración LIB-004](../../scripts/database/migrations/002_library_integrity.sql) se ejecuta dentro de la transacción de `database-schema`, tanto en instalaciones nuevas como existentes. Antes de modificar restricciones audita propietarios, referencias ausentes, ciclos, nombres vacíos y duplicados. Si encuentra problemas, aborta sin reparar ni borrar registros. Bloquea temporalmente escrituras en carpetas, asociaciones y favoritos; programa la actualización y respalda la base antes de aplicarla.

Las claves foráneas compuestas exigen el mismo propietario en padre e hijo y en carpeta y asociación. Su clave única de destino sigue el [contrato de PostgreSQL](https://www.postgresql.org/docs/16/ddl-constraints.html). El padre debe existir antes de insertar un hijo. Un trigger mantiene inmutables el ID, propietario y padre de cada carpeta; permite cambiar nombre y metadatos. Esto impide ciclos, incluidas inserciones de varias filas. Reubicar carpetas requerirá un diseño y migración explícitos; el endpoint de mover documentos no cambia padres de carpetas.

Los índices únicos existentes mantienen la comparación exacta de nombres por propietario y nivel, sensible a mayúsculas. Crear o renombrar con un nombre repetido devuelve HTTP 409 y revierte la transacción. Un nombre sin caracteres distintos de espacios se rechaza también en SQL; LIB-006 lo rechaza antes con HTTP 422. Si el padre desaparece entre la comprobación y la inserción, la API devuelve 404 y recupera la sesión.

Para inspeccionar una base histórica antes de actualizar, instala únicamente la función de auditoría desde la raíz con PowerShell y credenciales administrativas del entorno:

```powershell
Get-Content scripts/database/functions/002_library_integrity_audit.sql -Raw | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -c 'SELECT * FROM public.library_integrity_audit() WHERE affected > 0;'
```

La función es `SECURITY INVOKER` y no concede ejecución a `PUBLIC`. Los resultados son categorías y cantidades, sin nombres ni documentos. Si la migración falla, revisa los datos bajo control administrativo y decide su reparación; vuelve a ejecutar `database-schema` después. Para aplicar solo este archivo con `psql`, usa obligatoriamente `--single-transaction` y `ON_ERROR_STOP=1`.

## Diagnóstico LIB-001

Se revisaron todos los módulos del servicio, las doce operaciones, esquema, índices, cascadas, Compose, CI y los consumidores anteriores. Estos resultados corresponden a la base anterior a las correcciones.

Las fuentes principales son el [validador JWT](app/config/security.py), el [repositorio](app/infrastructure/database/repositories/library_repository_pg.py), las [rutas](app/interfaces/api/v1/routes/library_routes.py), los [esquemas HTTP](app/interfaces/api/v1/schemas/library_schema.py), el [esquema SQL](../../scripts/database/schemas/001_documents.sql), los [índices](../../scripts/database/indexes/001_indexes.sql) y [Compose](../../docker/compose/documents.yml).

| Área | Evidencia y efecto | Incremento |
| --- | --- | --- |
| Identidad | La base aceptaba identidades ambiguas y tokens sin vencimiento requerido. LIB-003 exige claims tipados, firma y token de acceso, sin fallbacks de identidad. | LIB-003 resuelto |
| Revocación | LIB-003 excluye asignaciones canceladas o expiradas en lecturas, altas y conteos. Las regresiones cambian el estado entre peticiones. | LIB-003 resuelto |
| Precedencia | LIB-003 prioriza columnas canónicas y limita el respaldo a valores nulos, igual que búsqueda y acceso. | LIB-003 resuelto |
| Grupos | LIB-003 exige membresía en el tenant efectivo para concesiones por grupo en documentos con tenant. | LIB-003 resuelto |
| Asociaciones incoherentes | LIB-003 bloquea lecturas ajenas; LIB-004 añade restricciones SQL de propietarios y coordina Google Drive con errores visibles. | LIB-004 resuelto |
| Nombres y conflictos | LIB-004 traduce índices existentes a HTTP 409. LIB-006 valida nombre tras trim, IDs, JSON y tamaño HTTP, y evita reflejar entradas o SQL en errores. | LIB-004 / LIB-006 resueltos |
| Concurrencia | LIB-005 usa altas idempotentes, retiradas SQL, serialización por usuario/documento y referencias protegidas frente a borrados. Pruebas independientes verifican esperas reales, orden y rollback. | LIB-005 resuelto |
| Cotas y orden | LIB-007 pagina cuatro listados, aplica desempates y conserva conteos por lote. Adapta consumidores, descarta respuestas obsoletas y retira métricas ficticias y consultas por carpeta. | LIB-007 resuelto |
| Configuración | La base importaba el entorno global, admitía CORS abierto y comprobaba solo vida del proceso. LIB-002 aplica configuración explícita, disponibilidad de dependencias, cierre con `finally` y opciones efectivas del pool, con pruebas. | LIB-002 resuelto |
| Ejecución | Se conecta como `postgres`, ejecuta como UID 0 e instala pytest y Ruff. LIB-002 añadió `library-tests` y CI; el rol mínimo, la imagen y las dependencias siguen pendientes. | LIB-008 |
| Mantenibilidad | Hay entidades, tipo vectorial, constantes de extracción y utilidades sin consumidores internos identificados. Retirarlos al cierre tras revisar imports. | LIB-008 |

Las observaciones comprobadas con datos sintéticos se distinguen de los riesgos de concurrencia pendientes. Este diagnóstico no equivale a una auditoría exhaustiva ni valida explotación de los avisos de dependencias.

## Decisiones para los siguientes incrementos

1. Mantener carpetas y favoritos privados por usuario. Una carpeta es organización personal y nunca concede lectura. No agregar tenant a las carpetas sin una decisión de producto y migración explícita.
2. Aplicar el contrato de lectura de DocumentSearchServices y DocumentAccessServices en listados, altas y conteos. Priorizar columnas canónicas, excluir asignaciones canceladas o expiradas y acotar grupos por membresía de tenant.
3. Permitir retirar marcadores personales cuyo acceso documental se revocó sin devolver datos del documento. Tratar carpetas ajenas igual que inexistentes y conservar su privacidad incluso ante administradores documentales.
4. Distinguir agregar de mover. Agregar admite varias carpetas propias; mover reemplaza las asociaciones personales por un destino o ninguno. Las pruebas concurrentes deben preservar esa semántica sin imponer unicidad global por documento.
5. Limitar el borrado de carpetas a carpetas y asociaciones. Auditar relaciones inválidas, ciclos y nombres existentes antes de imponer restricciones; no corregir datos mediante borrados silenciosos. Incluir al escritor de Google Drive en la migración.
6. Reutilizar convenciones de páginas y errores, con límites y desempate por ID. Adaptar juntos API, hook, ambas páginas y etiquetas. Los contadores deben representar datos reales o registros cargados; retirar métricas ficticias sin inventar tamaños de archivos.
7. Introducir pruebas PostgreSQL y de contrato antes de cada corrección. Mantener README operativo y AGENTS breve, enlazando el tablero sin duplicar planes en archivos de modernización. Esta organización sigue los principios de diagnóstico, evidencia y contexto mantenible de la [guía agents-first compartida](https://blandskron.github.io/agents-first-repo-docs/).

## Evidencia de la base

El 5 de noviembre de 2026 se construyó la imagen actual sin cambiar su código, `sha256:0672086190a8cb31f892b28131de6d75b53f457342b212a5054bbb99974d7203`.

- Una sonda temporal confirmó trece observaciones de identidad, permisos, conteos, nombres y conflictos sobre PostgreSQL. Usó claves temporales y datos sintéticos con transacción externa y savepoints; revirtió los registros al terminar. No abrió documentos ni llamó a servicios externos.
- Un contenedor aislado, sin puertos publicados, respondió HTTP 200 en ambos healthchecks, HTTP 401 al listar carpetas sin token y `Access-Control-Allow-Origin: *` ante un origen externo. Confirmó UID 0 y fue retirado.
- `ruff check --no-cache app` y `python -m pip check` aprobaron. No sustituyen pruebas de permisos ni auditoría de dependencias.
- `pip-audit` 2.10.1 examinó un inventario congelado antes de instalar el auditor, con 33 paquetes. Reportó 58 entradas de aviso en seis paquetes, con posibles duplicaciones o aliases: `cryptography 46.0.6`, `pip 25.0.1`, `PyJWT 2.12.1`, `pytest 8.3.5`, `python-dotenv 1.1.0` y `starlette 0.46.2`. LIB-008 actualizará y volverá a auditar. No se escaneó específicamente el sistema operativo de esta imagen.

## Arranque actual

Prepara `.env` según el [README principal](../../README.md). Desde la raíz ejecuta lo siguiente.

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-library-service
curl http://localhost:8006/api/v1/health
curl http://localhost:8006/api/v1/health/db
```

Compose pasa diez variables explícitas y monta únicamente la clave pública JWT en modo de solo lectura. No incorpora el entorno global al contenedor. PostgreSQL administrativo sigue pendiente de sustitución por el rol mínimo en LIB-008.

CORS permite por defecto `http://localhost:3000` y `http://127.0.0.1:3000`. Configura `LIBRARY_CORS_ORIGINS` como arreglo JSON para otros orígenes. Los orígenes externos no reciben autorización CORS; la autenticación HTTP continúa siendo obligatoria.

| Variable de Compose | Valor por defecto y efecto |
| --- | --- |
| `APP_ENV`, `LOG_LEVEL` | `local`, `INFO`. |
| `LIBRARY_DB_POOL_MIN_SIZE` | 1, capacidad de conexiones retenidas del pool. |
| `LIBRARY_DB_POOL_MAX_SIZE` | 10, máximo de conexiones simultáneas por proceso. |
| `LIBRARY_DB_TIMEOUT_SECONDS` | 30 segundos, espera del pool y timeout de conexión de psycopg. |

Los tamaños admiten 1 a 100 y el mínimo no puede superar al máximo. El timeout admite 1 a 300 segundos. El mínimo configura `pool_size`; el exceso permitido es máximo menos mínimo. Las conexiones se abren bajo demanda, sin preasignación, según el [contrato de QueuePool](https://docs.sqlalchemy.org/en/20/core/pooling.html). El timeout de conexión no limita la duración de una consulta SQL. En el proceso, estos parámetros se llaman `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE` y `DB_TIMEOUT_SECONDS`.

`health/db` comprueba una clave pública RSA válida y las columnas mapeadas de `documents`, `document_assignments`, `document_embeddings`, `document_folders`, `document_folder_items` y `document_favorites`, mediante consultas sin filas. Los errores de archivo, clave o PostgreSQL producen HTTP 503 con detalle genérico. `health` sigue disponible como comprobación de vida. El healthcheck de Compose usa `health/db` y lifespan libera el motor incluso si se interrumpe con una excepción.

Fuera de Compose, desde este directorio instala `requirements.txt` y configura `DATABASE_URL`, `AUTH_JWT_PUBLIC_KEY_PATH` y `AUTH_JWT_ALGORITHM`. Ejecuta `python -m uvicorn app.main:app --port 8006`. `CORS_ORIGINS` recibe un arreglo JSON. Settings solo lee el `.env` del directorio de trabajo y las variables del proceso; ya no busca `../../.env`. Las variables del proceso tienen prioridad. Configura el pool con sus nombres `DB_POOL_*` y `DB_TIMEOUT_SECONDS` fuera de Compose.

## Pruebas

Con el servicio y PostgreSQL iniciados, ejecuta desde la raíz.

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps library-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps library-tests ruff check --no-cache app tests
```

La suite usa claves temporales y PostgreSQL real. Cubre configuración, CORS, autenticación de las trece rutas, disponibilidad, recuperación del pool y cierre del motor. Las regresiones de LIB-003 incluyen tipos de claims, firma y algoritmo, propietario, asignador, destinatario, administradores, grupos y metadatos contradictorios. Comparan los tres listados y los conteos, revocan asignaciones entre peticiones y comprueban altas denegadas, carpetas privadas, vínculos incoherentes y limpieza personal de marcadores revocados. Los registros sintéticos se revierten con una transacción externa y savepoints; las tablas compartidas no se alteran.

LIB-004 añade pruebas de migración repetida, datos inválidos conservados ante rechazo, ciclos, propietarios, conflictos HTTP, desaparición del padre y cascadas que preservan documentos y favoritos. Monta los scripts SQL en solo lectura. `LIBRARY_TEST_DATABASE_URL` es una conexión administrativa exclusiva para pruebas: crea bases aisladas `lib004_<UUID>` y retira únicamente la base creada por cada caso. No la configures contra producción. Las pruebas ordinarias mantienen sus transacciones y savepoints.

LIB-005 reutiliza esas bases aisladas para sesiones independientes con datos confirmados. Las pruebas pausan una transacción antes de commit y observan `pg_blocking_pids` para comprobar la espera real de la segunda. Cubren reintentos, movimientos con y sin asociaciones previas, destino nulo, altas y retiradas, independencia por usuario/documento, borrados documentales y de ancestros, fallos antes del commit y recuperación de sesión. Drive prueba que su escritor espera el mismo bloqueo y asocia después de liberarlo.

Desde `frontend`, `npm test` incluye el conteo canónico con cero y el contrato de advertencias de importación. Ejecuta también `npm ci` y `npm run build` para validar cambios de sus consumidores. CI ejecuta además `drive-tests` y Ruff para el escritor compartido.

LIB-006 prueba fronteras de nombres, IDs, metadatos UTF-8 y profundidad; cuerpos fragmentados con tamaño declarado ausente o incorrecto, 413 con CORS y errores privados. Un guard impide llegar a métodos del caso de uso con entradas inválidas. PostgreSQL confirma el round trip de límites válidos, ausencia de escrituras rechazadas, conflictos y recuperación tras un trigger sintético que provoca un error SQL desconocido. También se verifica OpenAPI.

LIB-007 prueba páginas completas, parciales y vacías, desempates de fechas, límites y offsets, jerarquía, privacidad, revocación y consulta de marcadores por lote. Cuenta consultas para tamaños distintos de página. Las pruebas web ejercitan el controlador real con promesas diferidas: respuestas fuera de orden, cierre y cambio de carpeta, cambio de cliente, remontaje, doble clic, errores, favoritos no cargados y `count=0`; no requieren un proveedor externo.

CI arranca Library con su comprobación de disponibilidad y ejecuta `pip check`, las pruebas y Ruff. HTTPX está en la etapa Docker de pruebas. Las herramientas heredadas pytest y Ruff todavía forman parte de las dependencias de ejecución y se retirarán en LIB-008 junto con su actualización y auditoría.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
