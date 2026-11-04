# AuthServices

**AuthServices** es el microservicio de autenticación y gestión de usuarios del ecosistema Blandskron. Está construido con Django y Django REST Framework, usando JWT (JSON Web Tokens) para autenticación segura y flexible.

---

## Funcionalidades principales

### 1. **Autenticación y Autorización**
- **Login:** Autenticación de usuarios mediante usuario y contraseña. Devuelve tokens JWT (access y refresh) con información de roles, grupos y permisos.
- **Logout:** Invalida el refresh token (blacklist).
- **Refresh Token:** Permite renovar el access token usando un refresh token válido.
- **Perfil:** Endpoint para obtener los datos del usuario autenticado, incluyendo roles, grupos y permisos.

### 2. Gestión de usuarios

- El superadministrador gestiona las identidades globales y puede vincular cuentas existentes.
- Los cambios a grupos globales de Django también requieren superadministrador.
- Los administradores de empresa consultan a sus miembros y crean cuentas nuevas con su membresía en una única solicitud.
- El alta por empresa admite solo campos de identidad y datos de membresía. Los cambios posteriores a la membresía mantienen su empresa y su usuario.

### 3. **Infraestructura y Seguridad**
- Generación automática de claves RSA para firmar los JWT.
- Configuración de CORS para permitir integración con el frontend.
- Documentación OpenAPI/Swagger disponible en `/docs/`.
- Middleware de seguridad y manejo de sesiones.

---

## Endpoints principales

| Método | Ruta                        | Descripción                                      | Permisos           |
|--------|-----------------------------|--------------------------------------------------|--------------------|
| POST   | `/api/users/login/`         | Login y obtención de tokens JWT                  | Público            |
| POST   | `/api/users/logout/`        | Logout, invalida el refresh token                | Autenticado        |
| GET    | `/api/users/me/`            | Perfil del usuario autenticado                   | Autenticado        |
| POST   | `/api/users/token/refresh/` | Refresca el access token                         | Público            |
| GET | `/api/users/crud/` | Consulta de usuarios | Superadministrador o administrador de su empresa |
| POST, PUT, PATCH, DELETE | `/api/users/crud/` y detalle | Gestión de identidades globales | Superadministrador |
| POST | `/api/users/tenant-memberships/provision/` | Crea una cuenta nueva y su membresía. Recibe `tenant`, `username`, `password`, `role` y opcionalmente `area`, `email`, `first_name` y `last_name`. Devuelve la membresía. | Superadministrador o administrador de la empresa destino |
| POST | `/api/users/tenant-memberships/` | Vincula una identidad existente | Superadministrador |

## Vigencia de las sesiones

El token de acceso dura 10 minutos y el refresh dura 24 horas desde el login. Renovar devuelve un token de acceso con el rol, la empresa y los permisos actuales. Conserva la fecha de vencimiento del refresh.

El refresh se rechaza si la cuenta está desactivada, cambió su contraseña o cerró esa sesión en el servidor. Los refresh emitidos antes de incorporar la huella de contraseña requieren iniciar sesión de nuevo. Los servicios que verifican JWT sin consultar Auth pueden aceptar un access ya emitido hasta su vencimiento.

La API valida contraseñas nuevas con la política de Django. Las escrituras aceptan cadenas de hasta 128 caracteres y conservan los espacios ingresados. El cambio propio requiere la contraseña actual. Las contraseñas existentes pueden seguir usándose para iniciar sesión y se validan las nuevas al reemplazarlas.

## Límite de login y auditoría

La API y Django Admin comparten dos límites en PostgreSQL. Cada ventana fija de un minuto admite hasta 8 intentos por cuenta normalizada y 30 por dirección de conexión. La API responde con HTTP 429 y `Retry-After` al alcanzar un límite. Django Admin muestra un aviso en el formulario.

Auth usa `REMOTE_ADDR` como origen. Con un proxy, ese valor puede corresponder al proxy para todos los usuarios. El límite por cliente debe aplicarse en el proxy de confianza si el despliegue lo requiere.

El logger `blandskron.auth.audit` emite JSON a stderr para login aceptado, rechazado o limitado, cambio de contraseña y mutaciones administrativas exitosas por API. Incluye el ID interno del actor cuando corresponde. No incluye cuerpos, contraseñas, tokens, nombres de usuario ni IP. Programa la limpieza diaria de contadores antiguos:

```powershell
docker compose -f docker/docker-compose.yml exec -T auth-service python manage.py prune_login_budgets
```

Compose ejecuta las migraciones versionadas en `auth-migrate` antes de arrancar el servicio web. En una actualización desde AUTH-005A, `users.0002_loginattemptbudget` agrega la tabla de contadores.

## Arranque y migraciones

La imagen prepara los archivos estáticos durante la construcción. El servicio web ejecuta Gunicorn como UID y GID 10001. Al arrancar con los volúmenes existentes, el entrypoint ajusta únicamente los directorios de claves y los archivos PEM esperados, y luego cambia al usuario de servicio. El contenedor de migración corre con ese usuario y sin montar claves del emisor.

Si una migración falla, revisa `docker compose -f docker/docker-compose.yml logs auth-migrate` antes de reiniciar. Para volver a la imagen anterior, comprueba primero que pueda operar con el esquema ya migrado. El proceso web no ejecuta migraciones por su cuenta.

## Configuración por entorno

Compose usa `AUTH_ENV=development` y escucha en loopback. Para un despliegue separado, configura `AUTH_ENV=production` en el proceso de Auth e inyecta estos valores fuera del repositorio:

| Variable | Requisito |
|---|---|
| `DJANGO_SECRET_KEY` | Secreto aleatorio de al menos 50 caracteres. |
| `DJANGO_ALLOWED_HOSTS` | Hosts explícitos separados por comas. |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Opcional. Si se define, usa orígenes HTTPS completos sin rutas. |
| `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Valores explícitos. Usa un rol dedicado, distinto de `postgres`, y una contraseña de al menos 16 caracteres. |
| `DJANGO_PRIVATE_KEY_PATH`, `DJANGO_PUBLIC_KEY_PATH` | Rutas explícitas. Aprovisiona el PEM privado antes del arranque, con permisos exclusivos del propietario. |

El modo producción fuerza HTTPS y activa las cookies seguras. Si usas un proxy de TLS, configura Gunicorn para reconocer el esquema únicamente desde proxies de confianza.

## Roles de PostgreSQL en Compose

`auth-db-roles` aprovisiona los roles tras preparar el esquema documental. En bases existentes transfiere al rol `auth_migrate` únicamente las tablas administradas por Django. Luego `auth-migrate` aplica las migraciones y concede a `auth_runtime` acceso a las tablas y secuencias que usa el servicio. El rol web carece de permisos para crear objetos permanentes en `public`, modificar el historial de migraciones o leer la tabla de documentos.

Compose trae contraseñas locales de desarrollo para ambos roles. Para usar valores propios, exporta `AUTH_DB_RUNTIME_PASSWORD` y `AUTH_DB_MIGRATE_PASSWORD` en la sesión que ejecuta Compose. Mantén estos valores fuera del `.env` compartido por los servicios documentales. Los demás servicios de la demo conservan su configuración de PostgreSQL y quedan fuera de este incremento.

Para revertir a la versión anterior, reconstruye sus servicios Auth y conserva las tablas y los roles. El usuario anterior de Compose sigue teniendo acceso a las tablas aunque su propietario haya cambiado. No borres los roles ni reviertas la propiedad durante una recuperación rápida.

## Verificar la autorización

Desde la raíz, con PostgreSQL de Compose activo:

```powershell
docker compose -f docker/docker-compose.yml build auth-service
docker compose -f docker/docker-compose.yml run --rm --no-deps -T -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin1234 -e DJANGO_PRIVATE_KEY_PATH=/tmp/auth-test/private.pem -e DJANGO_PUBLIC_KEY_PATH=/tmp/auth-test/public.pem auth-service python manage.py test users core --noinput
```

Django crea una base de pruebas separada. El comando usa el operador de la base local para crearla, ya que el rol web carece de ese permiso. Los casos incluyen alta autorizada, escritura de privilegios globales, intentos de vincular o modificar una identidad ajena y referencias a otra empresa. El [plan de modernización](MODERNIZATION.md) detalla los incrementos siguientes.

## Actualizar desde el volumen JWT compartido

1. Detén el stack anterior con `docker compose -f docker/docker-compose.yml stop`. Conserva los volúmenes de base de datos y documentos.
2. Si la instalación conserva el administrador de demo anterior, cambia su contraseña antes de volver a publicar el puerto. Ejecuta `docker compose -f docker/docker-compose.yml run --build --rm auth-service python manage.py changepassword blandskronadmin`. La ejecución puntual omite los puertos del servicio.
3. Reconstruye y recrea el stack con `docker compose -f docker/docker-compose.yml up -d --build --wait`. Auth usa el par de los volúmenes nuevos. Los verificadores reciben solo el volumen público y se recrean para leer la clave nueva.
4. Inicia sesión de nuevo. Los JWT firmados con la clave anterior dejan de ser válidos. El volumen antiguo queda desmontado y puede conservar material sensible. Retíralo según la política de almacenamiento local cuando se haya confirmado la transición.

Solo Auth monta el volumen de firma. Si falta la clave pública, Auth la vuelve a publicar a partir de la privada existente. Para una rotación posterior, coordina una pausa del emisor y los verificadores y usa un par nuevo. La operación invalida sesiones, por lo que no conviene restaurar el par anterior como mecanismo de rollback.

---

## Estructura del proyecto

- `manage.py`: Comando principal de Django.
- `core/`: Configuración global, settings, rutas principales.
- `users/`: Lógica de usuarios, vistas, serializadores, endpoints.
- `docs/`: Documentación y rutas de OpenAPI.
- `Dockerfile`: Imagen para despliegue en contenedores.
- `.env.example`: Variables de entorno de ejemplo.

---

## Seguridad

- **JWT:** Tokens firmados con claves RSA generadas automáticamente.
- **Permisos:** Uso de permisos de Django y DRF para proteger endpoints.
- **CORS:** Solo orígenes permitidos pueden acceder a la API.
- **Contraseñas:** Almacenadas de forma segura usando el sistema de Django.

---

## Ejemplo de flujo de autenticación

1. **Login:**  
   `POST /api/users/login/`  
   Body: `{ "username": "...", "password": "..." }`  
   Respuesta: `{ "access": "...", "refresh": "...", "user": {...} }`

2. **Acceso a recursos protegidos:**  
   Usar el token `access` en el header `Authorization: Bearer ...`.

3. **Refrescar token:**  
   `POST /api/users/token/refresh/`  
   Body: `{ "refresh": "..." }`  
   Respuesta: `{ "access": "..." }`

4. **Logout:**  
   `POST /api/users/logout/`  
   Body: `{ "refresh": "..." }`  
   El token es invalidado.

---

## Documentación interactiva

- Accede a `/docs/` para la documentación OpenAPI y pruebas interactivas.

---

## Variables de entorno relevantes

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_PRIVATE_KEY_PATH`
- `DJANGO_PUBLIC_KEY_PATH`
- `DJANGO_CORS_ALLOWED_ORIGINS`

---

## Despliegue

1. Instala dependencias:  
   `pip install -r requirements.txt`
2. Ejecuta migraciones:  
   `python manage.py migrate`
3. Crea superusuario:  
   `python manage.py createsuperuser`
4. Ejecuta el servidor:  
   `python manage.py runserver 0.0.0.0:8000`

---

## Notas

- El microservicio está preparado para producción, pero revisa las variables de entorno y la configuración de seguridad antes de exponerlo.
- La gestión de usuarios y autenticación es centralizada para todos los servicios del ecosistema Blandskron.
