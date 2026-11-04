# ProfileServices

`ProfileServices` es el microservicio FastAPI encargado de exponer y actualizar perfiles de usuario. Complementa a `AuthServices`: la identidad, grupos y permisos vienen en el JWT, mientras que este servicio administra datos editables de perfil y avatar.

## Responsabilidades

- Consultar el perfil propio.
- Actualizar email, telefono, URL de foto y metadata adicional.
- Permitir a administradores listar y consultar perfiles.
- Permitir a administradores actualizar perfiles de terceros.
- Subir imagenes de perfil y exponerlas como archivos estaticos.
- Exponer grupos y permisos del usuario autenticado desde los claims del JWT.

## Endpoints

Todos los endpoints funcionales requieren `Authorization: Bearer <access_token>`.

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/v1/health` | Estado del servicio |
| GET | `/api/v1/health/db` | Estado de PostgreSQL |
| GET | `/api/v1/profile` | Obtiene el perfil del usuario autenticado |
| PUT | `/api/v1/profile` | Actualiza el perfil propio |
| GET | `/api/v1/profiles` | Lista perfiles, solo administradores |
| GET | `/api/v1/profiles/{user_id}` | Consulta perfil por usuario; propietario o admin |
| PUT | `/api/v1/profiles/{user_id}` | Actualiza perfil por usuario; propietario o admin |
| POST | `/api/v1/profile/upload` | Sube una imagen de perfil |

Las imagenes subidas se sirven desde `/static/{filename}`. El directorio fisico se configura con `PROFILE_UPLOADS_DIR`.

## Modelos principales

### `ProfileUpdateRequest`

```json
{
  "email": "usuario@example.com",
  "phone_number": "+56912345678",
  "profile_picture_url": "http://localhost:8015/static/avatar.jpg",
  "additional_info": {
    "department": "Legal",
    "position": "Analyst"
  }
}
```

### `ProfileResponse`

```json
{
  "profile_id": "uuid",
  "user_id": "123",
  "email": "usuario@example.com",
  "phone_number": "+56912345678",
  "profile_picture_url": "http://localhost:8015/static/avatar.jpg",
  "additional_info": {},
  "groups": ["admin"],
  "permissions": ["users.view_user"],
  "created_at": "2026-05-22T12:00:00Z",
  "updated_at": "2026-05-22T12:00:00Z"
}
```

### `ProfileUploadResponse`

```json
{
  "url": "http://localhost:8015/static/avatar.jpg"
}
```

## Configuracion

Variables relevantes:

- `DATABASE_URL`
- `AUTH_JWT_PUBLIC_KEY_PATH`
- `AUTH_JWT_ALGORITHM`
- `CORS_ORIGINS`
- `PROFILE_UPLOADS_DIR`

En Docker Compose, el servicio se publica en `http://localhost:8015` y monta `uploads/profile` en `/app/uploads`.

## Persistencia

Usa la tabla `user_profiles`, definida en `scripts/database/schemas/008_profiles.sql`, con `user_id` unico y `additional_info` en JSONB.

## Seguridad

- El perfil propio depende del `user_id`, `sub` o `username` presente en el JWT.
- Los endpoints de administracion validan rol/grupo/permisos mediante helpers de seguridad.
- El upload valida que el archivo sea una imagen usando Pillow antes de persistirlo.

Pendientes antes de produccion:

- limitar tamano de archivo y extensiones aceptadas
- normalizar/convertir imagenes para evitar contenido inesperado
- mover storage a un backend durable si se despliega fuera de un unico host
- agregar tests de permisos, upload y validacion de imagenes

## Ejecucion local

```powershell
cd backend/ProfileServices
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Con Docker Compose desde la raiz:

```powershell
docker compose -f docker/docker-compose.yml up profile-service
```
