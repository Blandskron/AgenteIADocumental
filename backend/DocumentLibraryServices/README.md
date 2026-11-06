# DocumentLibraryServices

Organiza documentos en carpetas personales, favoritos y una vista de documentos actualizados recientemente. Usa FastAPI, SQLAlchemy y el PostgreSQL compartido. El puerto local de Compose es `8006`.

LIB-001 estableció el diagnóstico y el plan. LIB-002 incorporó configuración y pruebas; LIB-003 valida identidad y unifica permisos documentales; LIB-004 refuerza la integridad SQL y coordina al escritor de Google Drive. Concurrencia, límites, paginación y privilegios de ejecución siguen en las tarjetas posteriores. El [tablero](../../ROADMAP.md#documentlibraryservices) es la fuente de tareas y [AGENTS.md](AGENTS.md) indica cómo intervenir el servicio.

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

Los dos healthchecks son públicos. Los listados devuelven arreglos. Solo `recent` admite un límite, entre 1 y 100, con 20 por defecto.

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
| `GET /library/recent?limit=20` | Documentos actualizados recientemente según el filtro de acceso actual. |
| `GET /library/favorites` | Favoritos según el filtro de acceso actual. |
| `POST /library/favorites/{document_id}` | `{"count":1/0}`. El cero puede indicar falta de acceso. |
| `DELETE /library/favorites/{document_id}` | `{"count":1/0}`. |

Hay doce operaciones de negocio y dos healthchecks. La respuesta documental contiene ID, nombre, MIME, estado, cantidad de fragmentos y fecha de actualización. La carpeta incluye ID, nombre, padre, propietario, metadatos, cantidad de documentos y fechas. No se publican rutas de almacenamiento ni vectores.

Crear recibe `name`, `parent_folder_id` opcional y `metadata`. Actualizar recibe `name` y `metadata` opcionales. Mover recibe `folder_id` opcional. Faltan cotas de longitud y tamaño JSON y validación del nombre después de eliminar espacios. Los cambios de contrato deben aplicarse junto con sus consumidores.

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

## Consumidores que deben revisarse juntos

- El [adaptador](../../frontend/src/features/document-library/api/document-library.api.js) normaliza arreglos. Un objeto paginado sin adaptar produciría listas vacías.
- El [hook](../../frontend/src/features/document-library/hooks/useDocumentLibrary.js) carga raíces, veinte recientes y favoritos con `Promise.all`. Actualiza favoritos de forma optimista e ignora el `count` devuelto. No protege respuestas frente a cambios de cliente o carpeta mientras hay peticiones en vuelo.
- [DocumentSearchPage](../../frontend/src/pages/DocumentSearchPage/DocumentSearchPage.jsx) consulta documentos por cada carpeta para construir etiquetas. El mapa acumula asociaciones antiguas y respuestas tardías pueden sobrescribir datos recientes. Algunas métricas usan constantes de demostración.
- [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) reutiliza carpetas y favoritos en la barra lateral. La interfaz no consume todo el CRUD ni la jerarquía expuesta por la API.
- [GoogleDriveImportServices](../GoogleDriveImportServices/README.md) inserta directamente en `document_folder_items`. LIB-004 comprueba la carpeta propia antes de consultar al proveedor y vuelve a comprobarla al asociar. Una asociación fallida conserva el documento importado, marca la importación `PARTIAL` y muestra una advertencia en DocumentSearchPage. Las pruebas usan un proveedor simulado, sin OAuth.

## Integridad y migración de carpetas

La [migración LIB-004](../../scripts/database/migrations/002_library_integrity.sql) se ejecuta dentro de la transacción de `database-schema`, tanto en instalaciones nuevas como existentes. Antes de modificar restricciones audita propietarios, referencias ausentes, ciclos, nombres vacíos y duplicados. Si encuentra problemas, aborta sin reparar ni borrar registros. Bloquea temporalmente escrituras en carpetas, asociaciones y favoritos; programa la actualización y respalda la base antes de aplicarla.

Las claves foráneas compuestas exigen el mismo propietario en padre e hijo y en carpeta y asociación. Su clave única de destino sigue el [contrato de PostgreSQL](https://www.postgresql.org/docs/16/ddl-constraints.html). El padre debe existir antes de insertar un hijo. Un trigger mantiene inmutables el ID, propietario y padre de cada carpeta; permite cambiar nombre y metadatos. Esto impide ciclos, incluidas inserciones de varias filas. Reubicar carpetas requerirá un diseño y migración explícitos; el endpoint de mover documentos no cambia padres de carpetas.

Los índices únicos existentes mantienen la comparación exacta de nombres por propietario y nivel, sensible a mayúsculas. Crear o renombrar con un nombre repetido devuelve HTTP 409 y revierte la transacción. Un nombre sin caracteres distintos de espacios se rechaza también en SQL. Las cotas y normalización completa de entradas siguen en LIB-006. Si el padre desaparece entre la comprobación y la inserción, la API devuelve 404 y recupera la sesión.

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
| Nombres y conflictos | LIB-004 rechaza nombres vacíos en SQL y traduce índices únicos existentes a HTTP 409. Los límites y normalización completa siguen pendientes. | LIB-004 resuelto / LIB-006 |
| Concurrencia | Favoritos y asociaciones usan consultar-antes-de-insertar. Mover ya retira e inserta en una transacción, pero no serializa movimientos simultáneos. Las carreras requieren pruebas con sesiones independientes. | LIB-005 |
| Cotas y orden | Carpetas, contenido de carpeta y favoritos no tienen límite. Recientes no permite recorrer páginas. Faltan desempates por ID. El conteo de fragmentos ya se hace por lote y debe conservarse. | LIB-006 / LIB-007 |
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

La suite usa claves temporales y PostgreSQL real. Cubre configuración, CORS, autenticación de las doce rutas, disponibilidad, recuperación del pool y cierre del motor. Las regresiones de LIB-003 incluyen tipos de claims, firma y algoritmo, propietario, asignador, destinatario, administradores, grupos y metadatos contradictorios. Comparan los tres listados y los conteos, revocan asignaciones entre peticiones y comprueban altas denegadas, carpetas privadas, vínculos incoherentes y limpieza personal de marcadores revocados. Los registros sintéticos se revierten con una transacción externa y savepoints; las tablas compartidas no se alteran.

LIB-004 añade pruebas de migración repetida, datos inválidos conservados ante rechazo, ciclos, propietarios, conflictos HTTP, desaparición del padre y cascadas que preservan documentos y favoritos. Monta los scripts SQL en solo lectura. `LIBRARY_TEST_DATABASE_URL` es una conexión administrativa exclusiva para pruebas: crea bases aisladas `lib004_<UUID>` y retira únicamente la base creada por cada caso. No la configures contra producción. Las pruebas ordinarias mantienen sus transacciones y savepoints.

Desde `frontend`, `npm test` incluye el conteo canónico con cero y el contrato de advertencias de importación. Ejecuta también `npm ci` y `npm run build` para validar cambios de sus consumidores. CI ejecuta además `drive-tests` y Ruff para el escritor compartido.

CI arranca Library con su comprobación de disponibilidad y ejecuta `pip check`, las pruebas y Ruff. HTTPX está en la etapa Docker de pruebas. Las herramientas heredadas pytest y Ruff todavía forman parte de las dependencias de ejecución y se retirarán en LIB-008 junto con su actualización y auditoría.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
