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
