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
| Integrada con seguimiento | AUTH-002 | Aislar mutaciones de empresa | La API y los claims protegen las relaciones. Quedan restricciones de persistencia y pruebas con sesiones concurrentes. |
| Hecha | AUTH-003 | Separar claves y bootstrap | Integrada con cuatro checks aprobados. Volúmenes separados, administrador explícito y puertos en loopback. |
| Hecha | AUTH-004 | Endurecer el ciclo de sesión | Integrada en main. Renovación con permisos vigentes y acceso de diez minutos. |
| Hecha | AUTH-005A | Aplicar la política de contraseñas de la API | Integrada en main. Las contraseñas rechazadas conservan la identidad y el hash anterior. |
| Hecha | AUTH-005B | Reducir abuso y auditar eventos | Integrada en main. La API y Django Admin comparten límites en PostgreSQL y emiten eventos JSON. |
| Hecha | AUTH-006A | Separar migración y arranque | Integrada en main. Compose migra primero y Gunicorn corre como UID 10001. |
| En revisión | AUTH-006B | Validar configuración por entorno | Producción exige secreto, hosts, rol de base y una clave preaprovisionada. HTTPS y cookies seguras se habilitan en ese modo. |
| Backlog | AUTH-006C | Separar permisos de PostgreSQL | Provisionar roles de migración y ejecución. Validar permisos positivos y denegación de DDL, y preparar reversión. |
| Backlog | AUTH-006D | Revisar dependencias e imagen | Clasificar los avisos de dependencias, actualizar donde corresponda y verificar la imagen final. |
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

## Evidencia de AUTH-003

- Solo Auth monta el volumen de firma. Los diez verificadores reciben el volumen público en solo lectura. La nueva comprobación de Compose cubre los montajes y las direcciones de escucha.
- El arranque con volúmenes nuevos rota la firma anterior. Si falta el PEM público, Auth lo recupera desde la clave privada existente. La clave privada nueva usa permisos de propietario en Linux.
- El stack local arrancó en loopback con el puerto alternativo de PostgreSQL. El servicio de búsqueda devolvió 401 para una firma antigua y 200 tras un login nuevo. El contenedor verificador pudo leer el PEM público y carecía del PEM privado.
- Pasaron 22 pruebas de Auth y el arranque con una base de pruebas nueva no creó un administrador. La guía indica cómo cambiar la contraseña de una cuenta de demo existente antes de reabrir el servicio.

## Evidencia de AUTH-005B

- Pasaron 33 pruebas en PostgreSQL. Se verificaron el límite compartido entre canales, la renovación de la ventana, el rechazo de un origen reenviado por el cliente y el límite exacto desde 12 conexiones independientes.
- `manage.py check` y `manage.py makemigrations --check --dry-run` pasaron. El entrypoint aplica las migraciones versionadas en lugar de generarlas.
- El README documenta la limpieza diaria de contadores y el comportamiento del límite por origen detrás de un proxy.

## Evidencia de AUTH-006A

- Compose aplicó la migración en un contenedor separado y Auth quedó sano sobre la base y los volúmenes locales existentes.
- El PID 1 de Gunicorn tuvo UID 10001. La clave privada conservó modo 0600 y la página de login de Django Admin respondió con HTTP 200.
- Pasaron 33 pruebas de Auth en PostgreSQL con el entrypoint nuevo y claves efímeras. CI comprueba también el UID efectivo de un comando iniciado desde la imagen.

## Evidencia de AUTH-006B

- Pasaron 37 pruebas de Auth en PostgreSQL, `manage.py check`, la comprobación de migraciones y Compose config.
- En un contenedor sin red, `manage.py check` aceptó una configuración de producción sintética y se comprobó que la redirección HTTPS y las cookies seguras estaban activadas. Las pruebas negativas cubren configuración ausente, valores de demo, hosts con comodines, orígenes HTTP y un PEM privado inexistente.
- `pip-audit` consultó las versiones fijadas y devolvió avisos para `cryptography==46.0.6`. El análisis de aplicabilidad, la actualización y la auditoría de la imagen quedan en AUTH-006D.

## Criterio de cierre por PR

- Alcance limitado a AuthServices y dependencias explícitas de su contrato.
- Pruebas de comportamiento permitido y denegado con identidades sintéticas. Los cambios de autorización deben cubrir sujetos, recursos y empresas diferentes.
- OpenAPI y consumidores revisados si cambia la API. PostgreSQL real cuando cambien constraints o migraciones.
- Evidencia reproducible en CI, riesgo residual explícito y reversión prevista para cambios de credenciales, claves o datos.
- Revisión humana para permisos, JWT, migraciones y despliegue antes de integrar.

## Referencia

Adopción progresiva basada en el [portal Agents First](https://blandskron.github.io/agents-first-repo-docs/), su [prompt maestro](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/prompts/agents-first-documentation-review.prompt.md) y el [playbook de ingeniería de repositorios](https://github.com/Blandskron/agents-first-repo-docs/blob/HEAD/library/domains/repository-engineering/playbooks/design-ai-first-repository.playbook.md). Consultados el 3 de noviembre de 2026. La documentación de Auth describe contratos verificados en este repositorio.
