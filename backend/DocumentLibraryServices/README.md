# DocumentLibraryServices

Organiza documentos en carpetas personales, favoritos y una vista de documentos actualizados recientemente. Usa FastAPI, SQLAlchemy y el PostgreSQL compartido. El puerto local de Compose es `8006`.

LIB-001 establece el diagnóstico y el plan. Las correcciones de permisos, integridad y operación descritas aquí siguen pendientes. El [tablero](../../ROADMAP.md#documentlibraryservices) es la fuente de tareas y [AGENTS.md](AGENTS.md) indica cómo intervenir el servicio.

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

Las rutas de negocio requieren `Authorization: Bearer <token>`. Los dos healthchecks son públicos. Los listados devuelven arreglos. Solo `recent` admite un límite, entre 1 y 100, con 20 por defecto.

| Método y ruta bajo `/api/v1` | Respuesta actual |
| --- | --- |
| `GET /health`, `GET /health/db` | `{"status":"ok"}`. DB consulta únicamente `documents`. |
| `GET /folders?parent_folder_id=...` | Carpetas del usuario en ese nivel, con `document_count`. Sin parámetro devuelve raíces. |
| `POST /folders` | Carpeta creada, HTTP 201. |
| `PATCH /folders/{folder_id}` | Carpeta actualizada. Cambia nombre y metadatos, no padre. |
| `DELETE /folders/{folder_id}` | `{"deleted":true/false}`. |
| `GET /folders/{folder_id}/documents` | Documentos asociados por el usuario. |
| `POST /folders/{folder_id}/documents/{document_id}` | `{"deleted":true/false}` aunque agrega una asociación. |
| `DELETE /folders/{folder_id}/documents/{document_id}` | `{"deleted":true/false}`. |
| `PATCH /library/documents/{document_id}/folder` | `{"success":true}` o HTTP 404. `folder_id: null` retira las asociaciones personales. |
| `GET /library/recent?limit=20` | Documentos actualizados recientemente según el filtro de acceso actual. |
| `GET /library/favorites` | Favoritos según el filtro de acceso actual. |
| `POST /library/favorites/{document_id}` | `{"count":1/0}`. El cero puede indicar falta de acceso. |
| `DELETE /library/favorites/{document_id}` | `{"count":1/0}`. |

Hay doce operaciones de negocio y dos healthchecks. La respuesta documental contiene ID, nombre, MIME, estado, cantidad de fragmentos y fecha de actualización. La carpeta incluye ID, nombre, padre, propietario, metadatos, cantidad de documentos y fechas. No se publican rutas de almacenamiento ni vectores.

Crear recibe `name`, `parent_folder_id` opcional y `metadata`. Actualizar recibe `name` y `metadata` opcionales. Mover recibe `folder_id` opcional. Faltan cotas de longitud y tamaño JSON y validación del nombre después de eliminar espacios. Los cambios de contrato deben aplicarse junto con sus consumidores.

## Consumidores que deben revisarse juntos

- El [adaptador](../../frontend/src/features/document-library/api/document-library.api.js) normaliza arreglos. Un objeto paginado sin adaptar produciría listas vacías.
- El [hook](../../frontend/src/features/document-library/hooks/useDocumentLibrary.js) carga raíces, veinte recientes y favoritos con `Promise.all`. Actualiza favoritos de forma optimista e ignora el `count` devuelto. No protege respuestas frente a cambios de cliente o carpeta mientras hay peticiones en vuelo.
- [DocumentSearchPage](../../frontend/src/pages/DocumentSearchPage/DocumentSearchPage.jsx) consulta documentos por cada carpeta para construir etiquetas. El mapa acumula asociaciones antiguas y respuestas tardías pueden sobrescribir datos recientes. Algunas métricas usan constantes de demostración.
- [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) reutiliza carpetas y favoritos en la barra lateral. La interfaz no consume todo el CRUD ni la jerarquía expuesta por la API.
- [GoogleDriveImportServices](../GoogleDriveImportServices/app/infrastructure/database/repositories/google_drive_repository_pg.py) inserta directamente en `document_folder_items`. Su caso de uso pasa `folder_id` sin comprobar aquí el propietario de la carpeta y descarta errores de asociación. LIB-004 debe coordinar este escritor, sin requerir OAuth para probar integridad SQL.

## Diagnóstico LIB-001

Se revisaron todos los módulos del servicio, las doce operaciones, esquema, índices, cascadas, Compose, CI y los consumidores anteriores. Estos resultados corresponden a la base anterior a las correcciones.

Las fuentes principales son el [validador JWT](app/config/security.py), el [repositorio](app/infrastructure/database/repositories/library_repository_pg.py), las [rutas](app/interfaces/api/v1/routes/library_routes.py), los [esquemas HTTP](app/interfaces/api/v1/schemas/library_schema.py), el [esquema SQL](../../scripts/database/schemas/001_documents.sql), los [índices](../../scripts/database/indexes/001_indexes.sql) y [Compose](../../docker/compose/documents.yml).

| Área | Evidencia y efecto | Incremento |
| --- | --- | --- |
| Identidad | El validador aceptó tokens firmados sin `user_id` ni `exp`, con `user_id: true` o con cero. Los fallbacks a `sub`, `username` o `unknown` pueden compartir biblioteca entre identidades ambiguas. | LIB-003 |
| Revocación | Una asignación `CANCELLED` siguió concediendo acceso; el documento apareció en carpeta y favoritos y siguió contando en la carpeta. El código tampoco excluye `EXPIRED`. | LIB-003 |
| Precedencia | Metadatos históricos concedieron acceso pese a contradecir propietario o tenant canónico. Búsqueda y acceso ya usan respaldo solo cuando falta la columna. | LIB-003 |
| Grupos | Un grupo concedió acceso a un documento de otro tenant sin membresía en ese tenant. | LIB-003 |
| Asociaciones incoherentes | Una fila sintética con propietario de asociación distinto al propietario de carpeta permitió listar un documento ajeno. Este caso requiere una asociación incoherente y no se reprodujo mediante la creación normal de Library. La BD no impone igualdad de propietarios. | LIB-003 / LIB-004 |
| Nombres y conflictos | Un nombre de espacios quedó almacenado vacío. Repetir un nombre raíz produjo `IntegrityError`, sin traducción a un conflicto HTTP. Ya existen índices únicos para nombres raíz y bajo un padre. | LIB-004 / LIB-006 |
| Concurrencia | Favoritos y asociaciones usan consultar-antes-de-insertar. Mover ya retira e inserta en una transacción, pero no serializa movimientos simultáneos. Las carreras requieren pruebas con sesiones independientes. | LIB-005 |
| Cotas y orden | Carpetas, contenido de carpeta y favoritos no tienen límite. Recientes no permite recorrer páginas. Faltan desempates por ID. El conteo de fragmentos ya se hace por lote y debe conservarse. | LIB-006 / LIB-007 |
| Configuración | Importa el entorno global, CORS admite `*` y el arranque comprueba solo `/health`. `health/db` no comprueba las tablas de biblioteca. Lifespan carece de `finally`; las opciones declaradas de tamaño y timeout del pool no se aplican al motor. | LIB-002 |
| Ejecución | Se conecta como `postgres`, ejecuta como UID 0 e instala pytest y Ruff. No hay pruebas del servicio ni trabajo propio en CI. | LIB-002 / LIB-008 |
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

Compose importa el `.env` global, usa PostgreSQL administrativo y CORS abierto. Son puntos pendientes de modernización, no la configuración final de publicación.

Fuera de Compose, desde este directorio instala `requirements.txt` y configura `DATABASE_URL`, `AUTH_JWT_PUBLIC_KEY_PATH` y `AUTH_JWT_ALGORITHM`. Ejecuta `python -m uvicorn app.main:app --port 8006`. `CORS_ORIGINS` recibe un arreglo JSON. Actualmente Settings también busca `../../.env`; revisa las variables resueltas sin imprimir secretos.

Para comprobar estáticamente la base, desde la raíz puedes ejecutar estos comandos.

```sh
docker build -t blandskron-library-baseline:lib001 backend/DocumentLibraryServices
docker run --rm blandskron-library-baseline:lib001 ruff check --no-cache app
docker run --rm blandskron-library-baseline:lib001 python -m pip check
```

Todavía no existe una suite ni un objetivo `library-tests`. LIB-002 añadirá esa base; los siguientes incrementos convertirán los casos diagnósticos en regresiones que exijan el comportamiento corregido.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
