# Modernización de AuthServices

Diagnóstico inicial sobre `main` en `fa74ac1`. Este es el primer servicio de la modernización de Blandskron Documental. Los cambios en consumidores se limitan al contrato de Auth cuando una prueba o una transición lo requiera.

## Mapa del servicio

| Superficie | Implementación actual | Contrato que se debe probar |
|---|---|---|
| HTTP | Django REST Framework en `users/urls.py`, OpenAPI y Django admin | Login, renovación, logout, perfil, contraseña y CRUD administrativo. |
| Identidad | Usuarios y grupos globales de Django | Separar la autoridad sobre cuentas globales de la administración por empresa. |
| Autorización | Membresías, áreas y grupos en `users/models.py` y reglas en vistas y serializadores | Evaluar actor, recurso actual, destino y estado de empresa en cada mutación. |
| JWT | Simple JWT con RS256 y claims de identidad y empresa | Documentar audiencia, emisor, tipo, vigencia, revocación y compatibilidad con los verificadores. |
| Persistencia | Django gestiona identidad y sesiones. El SQL del repositorio gestiona tablas multiempresa con modelos `managed=False` | Mantener una sola autoridad por tabla y probar el esquema con PostgreSQL real. |
| Arranque | Gunicorn y Compose. El entrypoint migra y crea el administrador inicial | Arranque determinista, configuración por entorno y privilegios mínimos. |
| Calidad | `users/tests.py` es un marcador. CI general cubre frontend, Compose y pgvector | Agregar un gate de Auth independiente del proveedor de IA. |

## Kanban

| Estado | ID | Incremento | Criterio de aceptación |
|---|---|---|---|
| En revisión | AUTH-000 | Mapa y diagnóstico Agents First | Alcance, fuentes, hallazgos, dependencias y orden de entrega documentados. |
| Hecha | AUTH-001 | Proteger cuentas globales | Integrada en main. Las mutaciones globales requieren superadministrador y el alta por empresa es atómica. |
| En revisión | AUTH-002 | Aislar mutaciones de empresa | Se valida propiedad y relaciones en Auth. La API protege borrados con referencias históricas y los claims omiten vínculos ajenos. El diagnóstico SQL prepara el endurecimiento de persistencia. |
| Backlog | AUTH-003 | Separar claves y bootstrap | El emisor posee la clave privada. Un verificador solo puede leer material público. Bootstrap explícito, configuración de demo limitada a loopback y plan de rotación con prueba de compatibilidad. |
| Backlog | AUTH-004 | Endurecer el ciclo de sesión | Renovación con claims vigentes, revocación ante cambios sensibles, vigencia documentada y pruebas de firma, tipo, expiración y credenciales antiguas. Probar el impacto en los consumidores. |
| Backlog | AUTH-005 | Reducir abuso y aplicar política de contraseñas | Validadores en todas las escrituras, límite verificable de intentos y registro de eventos administrativos sin secretos ni tokens. |
| Backlog | AUTH-006 | Hacer reproducible la operación | Separar migración y arranque, validar configuración segura, ejecutar como usuario sin privilegios, acotar permisos de base y revisar dependencias e imagen con evidencia. Registrar decisiones y estrategia de rollback. |
| Backlog | AUTH-007 | Completar la adopción Agents First | README humano, AGENTS local, contrato API y guías de pruebas, configuración, seguridad y operación enlazadas desde fuentes canónicas. Otra persona puede ejecutar las comprobaciones desde un clon limpio. |

## Secuencia y decisiones

1. Revisar AUTH-001 antes de integrar. El usuario nuevo y su membresía se crean en la misma transacción. El frontend y el backend deben actualizarse juntos porque el formulario ahora usa una sola ruta.
2. Cerrar las relaciones multiempresa en AUTH-002. Revisar el SQL actual y separar saneamiento de datos, nueva restricción y cambios de API cuando su reversión sea diferente.
3. Resolver claves, bootstrap y sesiones en incrementos separados. Registrar una decisión de arquitectura si cambian el contrato JWT o los límites de persistencia. Verificar el arranque limpio y la actualización de una instalación existente.
4. Consolidar las guías cuando existan comandos reales. Cargar primero el contexto del servicio y enlazar pruebas, configuración y datos bajo demanda. Crear una skill solo cuando el procedimiento se repita y tenga entradas, límites y evidencia estables.

## Evidencia de AUTH-001

La versión anterior aceptó la creación de una cuenta global por un administrador de empresa, la vinculación de una identidad ajena y el cambio de contraseña de una cuenta ya vinculada. Las pruebas se ejecutaron en un contenedor efímero con una base PostgreSQL separada.

El parche bloquea esas solicitudes, la reasignación de una membresía y la escritura de permisos mediante grupos globales por un usuario con acceso de staff. Pasaron 11 pruebas en PostgreSQL, `manage.py check` y el build del frontend. Se comprobó que OpenAPI incluye el nuevo endpoint. La generación general del esquema sigue mostrando advertencias y un diagnóstico previo en `MeView`. El trabajo de saneamiento de relaciones existentes y estado de empresa continúa en AUTH-002.

## Evidencia y seguimiento de AUTH-002

- Las actualizaciones conservan la empresa del recurso. Las áreas, membresías y asignaciones validan que la relación pertenezca a la misma empresa.
- Los administradores de empresas suspendidas pierden el acceso administrativo por esa membresía. El superadministrador conserva su acceso operativo.
- Los claims omiten grupos de otra empresa y ocultan referencias de área incoherentes. Los permisos de grupo se reemplazan en una transacción.
- El borrado de áreas requiere superadministrador por sus referencias documentales. El borrado de una membresía elimina sus asignaciones. La creación y actualización de asignaciones y el borrado de membresías bloquean la misma fila en PostgreSQL.
- El [diagnóstico SQL](../../scripts/database/checks/tenant_relationships.sql) cuenta inconsistencias sin modificar datos. La base local devolvió cero en los cinco controles. El saneamiento de otras instalaciones, las restricciones de base y una prueba concurrente con sesiones independientes quedan como seguimiento de persistencia.
- La revocación de permisos ya emitidos o reutilizados al renovar un JWT corresponde a AUTH-004.

## Criterio de cierre por PR

- Alcance limitado a AuthServices y dependencias explícitas de su contrato.
- Pruebas de comportamiento permitido y denegado con identidades sintéticas. Los cambios de autorización deben cubrir sujetos, recursos y empresas diferentes.
- OpenAPI y consumidores revisados si cambia la API. PostgreSQL real cuando cambien constraints o migraciones.
- Evidencia reproducible en CI, riesgo residual explícito y reversión prevista para cambios de credenciales, claves o datos.
- Revisión humana para permisos, JWT, migraciones y despliegue antes de integrar.

## Referencia

Adopción progresiva basada en el [portal Agents First](https://blandskron.github.io/agents-first-repo-docs/), su [prompt maestro](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/prompts/agents-first-documentation-review.prompt.md) y el [playbook de ingeniería de repositorios](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/library/domains/repository-engineering/playbooks/design-ai-first-repository.playbook.md). Consultados el 3 de noviembre de 2026. La documentación de Auth describe contratos verificados en este repositorio.
