# Operación y configuración de AuthServices

Todos los comandos de Compose parten de la raíz. Para el arranque inicial y la creación explícita del administrador, sigue el [README de AuthServices](../README.md).

## Flujo de arranque

1. `database-schema` prepara PostgreSQL y las tablas multiempresa del repositorio.
2. `auth-db-roles` aprovisiona `auth_migrate` y `auth_runtime`. Al actualizar, transfiere al rol de migración solo la propiedad de las tablas de Django.
3. `auth-migrate` aplica migraciones versionadas y concede acceso al rol web. Usa claves efímeras y carece del volumen de firma.
4. `auth-service` sirve HTTP en loopback con Gunicorn como UID 10001. El entrypoint prepara permisos de los volúmenes y la imagen incluye los archivos estáticos.

Si un paso falla, consulta su salida antes de reintentar:

```powershell
docker compose -f docker/docker-compose.yml ps -a auth-db-roles auth-migrate auth-service
docker compose -f docker/docker-compose.yml logs auth-db-roles auth-migrate auth-service
```

Para volver a la imagen anterior, conserva los volúmenes y verifica la compatibilidad del esquema aplicado. El usuario de base de la versión anterior de Compose sigue teniendo acceso a las tablas tras el cambio de propiedad.

## Entornos y secretos

Compose usa `AUTH_ENV=development`. Si necesitas credenciales locales propias para los roles, exporta `AUTH_DB_RUNTIME_PASSWORD` y `AUTH_DB_MIGRATE_PASSWORD` en el proceso que ejecuta Compose. El `.env` raíz también lo leen otros servicios, por lo que estas credenciales deben quedarse fuera de ese archivo.

En un despliegue separado con `AUTH_ENV=production`, inyecta las variables siguientes desde el sistema de secretos. La validación efectiva está en [core/environment.py](../core/environment.py).

| Variable | Requisito |
|---|---|
| `DJANGO_SECRET_KEY` | Secreto aleatorio de al menos 50 caracteres. |
| `DJANGO_ALLOWED_HOSTS` | Lista explícita de hosts, sin comodines. |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Opcional. Lista de orígenes HTTPS sin rutas. |
| `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Valores explícitos. Rol dedicado distinto de `postgres` y contraseña de al menos 16 caracteres. |
| `DJANGO_PRIVATE_KEY_PATH`, `DJANGO_PUBLIC_KEY_PATH` | Rutas explícitas. La clave privada debe existir antes del arranque y tener permisos de propietario. |

Producción fuerza HTTPS y activa cookies seguras. Si TLS termina en un proxy, configura Gunicorn para reconocer el esquema desde ese proxy de confianza. Los verificadores documentales solo reciben la clave pública.

## Actualización desde el volumen JWT compartido

1. Detén el stack anterior con `docker compose -f docker/docker-compose.yml stop` y conserva los volúmenes de datos.
2. Si conservas el administrador de demo anterior, cambia su contraseña antes de reabrir Auth con `docker compose -f docker/docker-compose.yml run --build --rm auth-service python manage.py changepassword blandskronadmin`.
3. Recrea el stack con `docker compose -f docker/docker-compose.yml up -d --build --wait` y vuelve a iniciar sesión.

La ejecución puntual del paso 2 no publica el puerto del servicio. Los JWT anteriores dejan de ser válidos tras la rotación. El volumen antiguo queda desmontado y puede contener material sensible. Retíralo según tu política de almacenamiento después de verificar la transición. Si solo falta el PEM público, Auth puede regenerarlo a partir de la clave privada actual.

## Límite de intentos y auditoría

La API y Django Admin comparten un límite de 8 intentos por cuenta normalizada y 30 por dirección de conexión en cada ventana fija de un minuto. El origen es `REMOTE_ADDR`. Detrás de un proxy puede ser la misma dirección para varios clientes.

El logger `blandskron.auth.audit` emite JSON a stderr para login, cambios de contraseña y mutaciones administrativas exitosas por API. Incluye un ID interno cuando corresponde. Omite cuerpos, contraseñas, tokens, nombres de usuario e IP. Programa la limpieza diaria de contadores antiguos:

```powershell
docker compose -f docker/docker-compose.yml exec -T auth-service python manage.py prune_login_budgets
```

Consulta las [pruebas y la evidencia de auditoría](TESTS.md) y el [tablero del repositorio](../../../ROADMAP.md) para el seguimiento de integridad de relaciones y los riesgos de la imagen.
