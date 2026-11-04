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
| En revisión | AUTH-001 | Proteger cuentas globales | El CRUD global y la vinculación de cuentas existentes requieren superadministrador. El alta por empresa es atómica y la UI usa esa ruta. Las pruebas positivas y negativas de Auth se ejecutan sobre PostgreSQL. |
| Backlog | AUTH-002 | Aislar mutaciones de empresa | Validar origen, destino y pertenencia de áreas, grupos y sujetos para POST, PUT, PATCH y DELETE. Probar empresa suspendida, dos empresas y escritura concurrente. Detectar datos incoherentes antes de activar restricciones SQL. |
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

## Criterio de cierre por PR

- Alcance limitado a AuthServices y dependencias explícitas de su contrato.
- Pruebas de comportamiento permitido y denegado con identidades sintéticas. Los cambios de autorización deben cubrir sujetos, recursos y empresas diferentes.
- OpenAPI y consumidores revisados si cambia la API. PostgreSQL real cuando cambien constraints o migraciones.
- Evidencia reproducible en CI, riesgo residual explícito y reversión prevista para cambios de credenciales, claves o datos.
- Revisión humana para permisos, JWT, migraciones y despliegue antes de integrar.

## Referencia

Adopción progresiva basada en el [portal Agents First](https://blandskron.github.io/agents-first-repo-docs/), su [prompt maestro](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/prompts/agents-first-documentation-review.prompt.md) y el [playbook de ingeniería de repositorios](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/library/domains/repository-engineering/playbooks/design-ai-first-repository.playbook.md). Consultados el 3 de noviembre de 2026. La documentación de Auth describe contratos verificados en este repositorio.
