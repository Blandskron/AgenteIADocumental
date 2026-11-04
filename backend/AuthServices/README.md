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

## Verificar la autorización

Desde la raíz, con PostgreSQL de Compose activo:

```powershell
docker compose -f docker/docker-compose.yml build auth-service
docker compose -f docker/docker-compose.yml run --rm --no-deps -T --entrypoint python auth-service manage.py test users --noinput
```

Django crea una base de pruebas separada. Los casos incluyen alta autorizada, escritura de privilegios globales, intentos de vincular o modificar una identidad ajena y referencias a otra empresa. El [plan de modernización](MODERNIZATION.md) detalla los incrementos siguientes.

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
