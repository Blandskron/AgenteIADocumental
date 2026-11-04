# AuthServices

**AuthServices** es el microservicio de autenticación y gestión de usuarios del ecosistema Blandskron. Está construido con Django y Django REST Framework, usando JWT (JSON Web Tokens) para autenticación segura y flexible.

---

## Funcionalidades principales

### 1. **Autenticación y Autorización**
- **Login:** Autenticación de usuarios mediante usuario y contraseña. Devuelve tokens JWT (access y refresh) con información de roles, grupos y permisos.
- **Logout:** Invalida el refresh token (blacklist).
- **Refresh Token:** Permite renovar el access token usando un refresh token válido.
- **Perfil:** Endpoint para obtener los datos del usuario autenticado, incluyendo roles, grupos y permisos.

### 2. **Gestión de Usuarios (CRUD)**
- **Solo para administradores.**
- Crear, listar, actualizar y eliminar usuarios.
- Asignación de grupos y roles.
- Serialización enriquecida con información de permisos y grupos.

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
| CRUD   | `/api/users/crud/`          | Gestión completa de usuarios (admin)             | Solo admin         |

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
