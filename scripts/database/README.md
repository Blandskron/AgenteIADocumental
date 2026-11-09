# Esquema y operación de PostgreSQL

`run_all.sql` coordina el esquema compartido; Django gestiona identidad/sesión de Auth. No ejecutar migraciones individuales fuera del orden y las condiciones documentadas por su servicio. [Tablero](../../ROADMAP.md), [Auth](../../backend/AuthServices/README.md) y [reglas del repositorio](../../AGENTS.md).

## Preflight multiempresa — PLAT-001A

Después de cargar el esquema y las migraciones de Auth, el preflight consulta una instantánea repeatable-read, read-only, con timeout de sentencia de 30 s y espera de locks de 5 s. Devuelve un objeto JSON versión 1 con trece conteos, suma `issues` y `requires_review`. No escribe, repara, elimina ni devuelve IDs/nombres/metadata. No se ejecuta automáticamente durante bootstrap ni solicita nuevas concesiones para roles de servicio.

Desde la raíz, contra el PostgreSQL de la configuración elegida:

```sh
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema psql -h postgres -U postgres -d documents_db -X -q -v ON_ERROR_STOP=1 -f /schema/checks/tenant_preflight.sql
```

El comando Compose usa las credenciales de desarrollo de `database-schema`. Fuera de ese entorno, usar una conexión operativa autorizada con SELECT en las tablas indicadas; no ampliar roles de ejecución para hacer la auditoría. No pasar claves por CLI ni guardar salidas junto con credenciales. `tenant_relationships.sql` conserva la consulta tabular histórica de cinco relaciones; el preflight nuevo amplía el alcance sin romper ese uso manual.

| Comprobaciones | Significado |
| --- | --- |
| area/membership/group/document tenant_missing | Empresa referenciada ausente; tenant nulo de documento global sigue admitido. |
| area_parent_invalid, membership_area_invalid, document_area_invalid | Referencia ausente o de otra empresa. Un documento con área y sin empresa requiere revisión. |
| membership_user_missing | No coincide con un ID canónico de Auth (`id::text`), incluidos usuarios eliminados. No presume una reparación ni borra historia. |
| permission_group_missing, assignment_group_invalid | Grupo inexistente o asignación en otra empresa. |
| assignment_without_membership | Falta la membresía de ese usuario en esa misma empresa; no exige que esté activa para conservar una asignación deshabilitada. |
| area_cycle_reachable | Áreas que llegan a un ciclo, incluidos sus descendientes; no es el número de ciclos. |
| area_depth_unresolved | La consulta agotó 256 nodos antes de demostrar el final. Requiere inspección, no se declara ciclo ni consistencia. |

El código de éxito de psql solo confirma que la consulta terminó: revisar `requires_review`, no interpretarlo como ausencia de inconsistencias. Una fila puede aparecer en varios conteos: `issues` no es cantidad de registros únicos. Un resultado en cero es diagnóstico de esa instantánea, no garantiza escrituras futuras ni concurrencia. Falta de tablas/permisos o timeout produce error y no un informe limpio. La consulta recursiva está acotada en profundidad; el timeout limita el coste total, incluido un grafo grande. El test de CI solo usa datos sintéticos y revierte todas las fixtures, también las que simulan un restore incompleto.

## Escritores y decisiones antes de imponer restricciones

| Frontera | Escritores actuales y contrato que debe conservarse |
| --- | --- |
| Empresas, áreas, membresías y grupos | Auth: `users/views.py`, serializadores `TenantScopedSerializer`/provision y modelos no gestionados. API impide cambiar empresa y valida relaciones; asignaciones/borrado de membresía comparten lock. SQL todavía permite cruces/ciclos. |
| Permisos y asignaciones de grupos | Auth administra permisos y exige membresía al asignar. Helpers de otros servicios leen esas relaciones; no son sus escritores funcionales. |
| Documento, empresa y área | Ingesta estampa identidad/empresa/área en `DocumentWriterPg.create`; el bootstrap también recupera columnas desde metadata heredada. Borrados de áreas/empresas y sus acciones FK afectan estas referencias. Documentos globales sin área siguen siendo válidos. |
| SQL operativo y pruebas | `run_all.sql`, provisionadores, sondas y fixtures escriben tablas compartidas. Deben revisarse junto con los contratos; no retirar pruebas de datos heredados para ocultar una incompatibilidad. |

La siguiente migración debe usar claves compuestas por empresa para padre de área, área de membresía/documento y grupo de asignación, y una FK por empresa/usuario de asignación a membresía. Preservar SET NULL solo en la referencia opcional y cascadas de asignaciones al borrar membresía; no convertir un borrado de empresa en un traslado o borrado documental. Revisar primero el orden de borrado y el caso documento con tenant nulo. PostgreSQL 16 permite listas de columnas en SET NULL y exige una clave única compatible para el destino: [documentación oficial](https://www.postgresql.org/docs/16/ddl-constraints.html).

Ciclos requieren un protocolo probado bajo concurrencia, no un CHECK que lea otras filas ni solo un preflight. Las referencias textuales a usuarios Auth requieren acordar ciclo de vida y compatibilidad antes de una FK tipada. Ningún reporte autoriza cambiar históricos: inventariar fuera de Git, decidir reparación explícita, respaldar, comparar versión/hash y validar el esquema resultante. No se añaden constraints ni reparación automática en PLAT-001A. El cierre de PLAT-001 exige migración, todos los escritores y pruebas concurrentes con logins reales.

## Validación sintética

Solo en un proyecto/DB de pruebas dedicado con Auth inicializado:

```sh
docker compose --env-file .env.example -p <proyecto-aislado> -f docker/docker-compose.yml run --rm --no-deps database-schema psql -h postgres -U postgres -d documents_db -X -q -v ON_ERROR_STOP=1 -f /schema/tests/tenant_preflight.sql
```

El test compara deltas contra una línea base, contempla datos válidos/globales, cruces, huérfanos, ciclo propio/de dos nodos/descendiente, cadena profunda y privacidad. Dentro de su transacción sintética usa `session_replication_role=replica` para simular referencias rotas de un restore; requiere el usuario de prueba administrador y siempre termina con ROLLBACK. No ejecutar ese test en una base de uso real. El wrapper operativo anterior no utiliza esa opción ni necesita escribir.

## Asignaciones por empresa — primer incremento PLAT-001B

La migración optativa `migrations/003_tenant_assignments.sql` activa dos FKs validadas: (tenant_id,group_id) al grupo y (tenant_id,user_id) a la membresía. Ambas conservan ON DELETE CASCADE: retirar membresía o grupo elimina solo las asignaciones relacionadas. No exige membresía activa; deshabilitarla conserva su configuración. No cambia roles ni repara históricos.

Con respaldo y escritores detenidos, ejecutar primero el preflight y revisar cualquier inconsistencia fuera de Git. En una conexión operativa autorizada, ejecutar la migración completa con ON_ERROR_STOP; toma locks de escritura sobre las tres tablas, espera cinco segundos como máximo y limita sentencias a 60 s. Si encuentra asignaciones cruzadas/huérfanas, informa solo conteos y revierte todo. Comprueba definición y validación de restricciones homónimas; una deriva exige revisión, nunca se sustituye silenciosamente.

```sh
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema psql -h postgres -U postgres -d documents_db -v ON_ERROR_STOP=1 -f /schema/migrations/003_tenant_assignments.sql
```

La activación es explícita; 004 añade áreas/documentos y se describe abajo. El despliegue general y los consumidores se validan antes del cierre; no forma parte de run_all.sql todavía. No desplegarla automáticamente sobre históricos. Auth ya verifica empresa/membresía y serializa asignación/borrado de membresía; esta capa impide también SQL directo inconsistente. Otros servicios solo leen estas asignaciones. Las carreras pueden producir 23503: consumidores que activen la migración deben tratarlo como conflicto y recargar, sin reintento ciego. Auth e ingesta traducen los conflictos conocidos según la sección siguiente; la activación general y la validación integral conservan sus tarjetas.

Las pruebas de test_tenant_assignments.py usan una DB separada cuyo nombre empieza por plat_assignments_, login real auth_runtime, bloqueos observados en pg_stat_activity y ambos órdenes entre inserción y borrado de grupo/membresía. Verifican repetibilidad, rechazo de deriva y preservación de datos ante preflight fallido. Nunca apuntarlas a documents_db; CI crea y elimina su DB sintética.

## Áreas y documentos — segundo incremento PLAT-001B

`migrations/004_tenant_area_relations.sql` activa en una transacción las asignaciones anteriores y las relaciones de padre de área, área de membresía y área documental dentro de su misma empresa. Ejecutar después del esquema base, respaldo y revisión del preflight, con escritores detenidos. Es activación explícita; todavía no se incorpora a run_all.sql mientras se completa PLAT-001C y la validación transversal de consumidores.

```sh
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema psql -h postgres -U postgres -d documents_db -v ON_ERROR_STOP=1 -f /schema/migrations/004_tenant_area_relations.sql
```

La migración toma locks antes de revisar los datos, limita la espera a cinco segundos y cada sentencia a 60 s. Rechaza cruces/huérfanos con conteos, sin reparar ni borrar; una definición homónima inesperada provoca rollback. También verifica tipo, generación y expresión de la nueva columna, nulabilidad de las referencias y acciones de las FKs anteriores. Una FK adicional sobre esas referencias se rechaza: no se permite que un CASCADE inesperado contradiga la conservación. Añadir una columna STORED puede reescribir documents: reservar ventana de mantenimiento y capacidad, no asumir un ALTER sin bloqueo.

Las áreas padre y de membresía usan SET NULL únicamente en la referencia opcional, preservando tenant_id. Documentos globales y documentos de empresa sin área siguen admitidos. Para distinguirlos del caso inválido área sin empresa, documents añade owner_area_tenant_id, calculada por PostgreSQL cuando hay área. Una FK MATCH FULL diferida valida el par al commit. La columna no se acepta como dato del cliente ni se expone en DTO; no cambia los campos de usuario ni metadata histórica.

Se conserva y verifica el SET NULL original de owner_area_id. La FK compuesta documental usa NO ACTION diferido porque PostgreSQL 16 no permite SET NULL en una FK que contiene una columna generada; las acciones originales limpian las referencias antes de comprobar el estado final. Así, borrar área conserva empresa/documento; borrar empresa conserva documento/propietario/storage y deja empresa/área nulas. No se añade función privilegiada ni permisos nuevos. [Columnas generadas](https://www.postgresql.org/docs/16/ddl-generated-columns.html) y [FK, MATCH FULL y diferibilidad](https://www.postgresql.org/docs/16/sql-createtable.html).

Auth devuelve 409 saneado solo para las violaciones conocidas de estas relaciones (también asignaciones); otros errores conservan su manejo. OpenAPI documenta ese conflicto. Ingesta revierte flush/commit, devuelve ConflictError/HTTP409 y la capa de carga retira el storage recién creado. No repite cargas ni inicia procesamiento tras el conflicto. Drive mantiene su política conservadora de revisión para respuestas downstream no clasificadas; el cierre de activación debe revisar esa experiencia junto con PLAT-001C/WEB-001.

Pruebas nuevas: doce casos PostgreSQL/Auth (API con actor sintético y login DB real), seis de ingesta con embedding_runtime/auth_runtime y carreras entre carga y borrado en ambos órdenes. Comprueban nulos válidos/indebidos, conservación documental al borrar por SQL/HTTP, rollback y sesión reutilizable, atomicidad combinada, deriva de FK/columna generada y bloqueo real observado. El arnés local liviano ejecuta el código real de ingesta sin OCR/IA; CI usa su imagen de pruebas completa. La FK por sí sola permite ciclos del mismo tenant; la migración siguiente añade su protección.

## Jerarquía concurrente — primer incremento PLAT-001C

`migrations/005_tenant_hierarchy.sql` incorpora las restricciones de asignaciones/áreas/documentos anteriores y el guard de jerarquía en una sola transacción. Sigue siendo optativa; la activación general requiere completar el ciclo de vida de usuarios y la coordinación de Drive. Con respaldo, preflight revisado y escritores detenidos:

```sh
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema psql -h postgres -U postgres -d documents_db -v ON_ERROR_STOP=1 -f /schema/migrations/005_tenant_hierarchy.sql
```

El preflight rechaza ciclos existentes y cadenas cuyo final no demuestra en 256 nodos. Solo informa conteos y revierte; no modifica historia para permitir el despliegue. Los locks de activación esperan hasta cinco segundos y las sentencias hasta 60 s. La migración comprueba tipo/default del contador, cuerpo/lenguaje/configuración/permisos de la función y definición/estado del trigger; una deriva no se reemplaza. Una activación fallida revierte también columnas y funciones nuevas.

Las áreas conservan movimientos y separación del padre. Su identidad y empresa son inmutables; cada padre debe existir previamente en la misma empresa, por lo que los importadores deben insertar padres antes que hijos. El trigger BEFORE comprueba los ancestros con UNION, que termina incluso frente a un ciclo heredado. La eliminación de una relación no puede crear ciclos y respeta los SET NULL/cascadas existentes. Se conservan documentos, propietario histórico y storage al borrar áreas/empresas.

Cada relación nueva o modificada con padre incrementa `tenants.area_revision` en la misma transacción, antes de consultar ancestros. Ese UPDATE serializa cambios de topología de una empresa; empresas distintas usan filas distintas. También actualiza `tenants.updated_at` por el trigger existente. El contador es interno: no se añade al modelo/API ni necesita permisos nuevos. La función es VOLATILE, SECURITY INVOKER, con search_path fijado y EXECUTE público revocado; usa los permisos existentes de Auth. Los operadores que escriban áreas directamente necesitan SELECT de áreas y UPDATE de tenants; no ampliar roles lectores para ello.

Repetir el bootstrap base y la activación conserva los campos documentales de contenido, identidad y storage. El bootstrap existente sí modifica `documents.updated_at` mediante sus UPDATE de normalización; una comparación de conservación debe distinguir esa marca temporal. La migración 005 no normaliza documentos ni repara históricos.

En Read Committed, las consultas VOLATILE posteriores a la espera ven el cambio confirmado del primer escritor. En Repeatable Read/Serializable el UPDATE real del contador rechaza al contendiente con snapshot anterior mediante 40001. Un mero lock sin cambio de versión no ofrece esa garantía. Véanse [visibilidad de funciones](https://www.postgresql.org/docs/16/xfunc-volatility.html) y [aislamiento](https://www.postgresql.org/docs/16/transaction-iso.html). Pueden producirse deadlocks con otras mutaciones: PostgreSQL aborta una transacción y no se hace reintento implícito. Auth devuelve 409 saneado para ciclos/identidad inmutable y SQLSTATE 40001/40P01/55P03; revisar una relación válida y recargar antes de una nueva mutación. Errores desconocidos conservan su manejo.

`tests/test_tenant_hierarchy.py` exige DB `plat_hierarchy_*` sintética, logins postgres/auth_runtime de prueba, bootstrap y migración 005. CI copia cuerpo/prueba a `/tmp/tenant-hierarchy.sql` y `/tmp/test_tenant_hierarchy.py` en Auth, ejecuta con POSTGRES_DB/PLAT_TEST_DATABASE apuntando a esa DB y retira la base al terminar. Son 19 pruebas: movimientos/ciclos/identidad, carreras observadas en los tres aislamientos y rollback, empresas independientes, conservación documental, HTTP 409/conexión reutilizable, repetibilidad, permisos, deriva e historia corrupta/profunda sin reparación. Las fixtures rotas se revierten dentro de su transacción. Esto cierra la protección optativa de jerarquía; identidad Auth, Drive y activación transversal siguen pendientes en PLAT-001B/C.
