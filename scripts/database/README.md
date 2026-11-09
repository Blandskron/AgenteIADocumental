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
