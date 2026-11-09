# Contrato de AuthServices

Base local: `http://localhost:8001`. Consulta [OpenAPI](http://localhost:8001/docs/api/schema/), [Swagger](http://localhost:8001/docs/api/schema/swagger-ui/) o [ReDoc](http://localhost:8001/docs/api/schema/redoc/). Las rutas de la API están en [users/urls.py](../users/urls.py) y las de documentación interactiva en [core/openapi.py](../core/openapi.py).

`/` y `/docs/` redirigen a Swagger. Una ruta desconocida devuelve 404.

## Sesión y perfil

| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /api/users/login/` | `username`, `password` | 200 con `access`, `refresh` y `user`. 400 con credenciales inválidas. 429 con `Retry-After` si excede el límite. |
| `POST /api/users/token/refresh/` | `refresh` | 200 con `access` y permisos actuales. 401 si el refresh es inválido, expiró, fue revocado o cambió la contraseña. |
| `GET /api/users/me/` | JWT de acceso en `Authorization: Bearer` | 200 con el perfil vigente, roles y membresías. |
| `POST /api/users/logout/` | JWT de acceso y `refresh` | 205 cuando se revoca el refresh enviado. |
| `POST /api/users/change-password/` | JWT de acceso, `old_password`, `new_password` | 200 al guardar. 400 si la contraseña actual o la nueva no pasa la validación. |

El JWT usa RS256. El access dura 10 minutos y el refresh dura 24 horas desde el login. Renovar recalcula roles y permisos, y conserva el vencimiento del refresh. El acceso ya emitido puede seguir funcionando hasta su vencimiento en verificadores sin estado. Las contraseñas nuevas tienen un máximo de 128 caracteres y conservan los espacios ingresados.

El perfil incluye identidad global, `roles`, `tenant_memberships`, `active_tenant_id`, `active_area_id`, `active_role` y `active_permissions`. Auth selecciona el contexto activo entre membresías activas de empresas activas, con prioridad `TENANT_ADMIN`, `LEADER`, `USER`. El JWT conserva estos nombres para los consumidores documentales y el frontend. Consulta los campos y tipos en el esquema OpenAPI.

## Administración

| Ruta | Límite de autorización |
|---|---|
| `/api/users/crud/` | El superadministrador gestiona identidades globales. El administrador de empresa puede consultar a sus miembros. |
| `/api/users/groups/`, `/api/users/permissions/` | La lectura requiere staff. Las mutaciones de grupos globales requieren superadministrador. |
| `/api/users/tenants/` | Gestión reservada al superadministrador. |
| `/api/users/tenant-memberships/provision/` | Crea una cuenta y su membresía en una transacción. Recibe `tenant`, `username`, `password`, `role` y opcionalmente `area`, `email`, `first_name` y `last_name`. Devuelve la membresía. |
| `/api/users/tenant-memberships/` | Solo el superadministrador puede vincular una cuenta existente. Las mutaciones por empresa se limitan a la empresa administrada y conservan la identidad de la membresía. |
| `/api/users/tenant-areas/`, `/api/users/tenant-groups/`, `/api/users/tenant-user-groups/` | Las referencias respetan la empresa del recurso. El borrado de áreas requiere superadministrador. |

Un JWT válido identifica al actor. El alcance de la operación se resuelve en [users/views.py](../users/views.py) y [users/serializers.py](../users/serializers.py). Evita incluir tokens reales en ejemplos o diagnósticos.

### Conflictos de relaciones multiempresa

Si una referencia desaparece entre validación y escritura, las mutaciones de empresa/áreas/membresías/grupos/asignaciones pueden devolver 409 con un detalle genérico. Recargar antes de reintentar; no hay reintento automático ni valores SQL en la respuesta. La validación normal de una referencia de otra empresa sigue devolviendo 400. OpenAPI incluye 409 también en provision. La activación SQL y su alcance se describen en [la guía compartida](../../../scripts/database/README.md#áreas-y-documentos--segundo-incremento-plat-001b).

Con la migración optativa de jerarquía, un área puede cambiar de padre o quedar sin padre, pero no formar ciclos. El padre debe existir previamente en la misma empresa. Un ciclo rechazado por SQL devuelve el mismo 409 saneado: elegir una relación válida y recargar. La identidad y empresa del área son inmutables. Conflictos de serialización, deadlock o espera de lock agotada también devuelven 409; revisar el estado antes de enviar una nueva mutación. Los errores de conexión o restricciones desconocidas no se reclasifican. No se exponen contador interno, SQL ni identificadores del conflicto.

### Ciclo de vida de cuentas y membresías

Al vincular una cuenta existente, `user_id` conserva el contrato textual y debe identificar una cuenta Auth existente mediante su ID decimal positivo canónico (hasta diez dígitos, sin ceros iniciales, espacios ni dígitos Unicode). Una referencia inválida devuelve 400. Si la cuenta desaparece después de validar y está aplicada la migración optativa 006, la escritura devuelve 409 saneado y no crea la membresía. La referencia tipada interna no forma parte del DTO.

Con esa migración, eliminar una cuenta retira sus membresías de todas las empresas y sus asignaciones de grupos. No borra grupos, documentos, storage ni sus IDs históricos de propietario. Deshabilitar una cuenta conserva su configuración; Auth rechaza sus sesiones según el contrato vigente. Los verificadores sin estado mantienen la limitación de vencimiento del access indicada arriba. La eliminación no constituye una operación de borrado documental: esa operación usa el contrato de DocumentAccessServices.
