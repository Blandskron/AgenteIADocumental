# Verificación de AuthServices

Usa datos sintéticos. Desde la raíz, crea un `.env` de desarrollo si falta y arranca Auth con PostgreSQL:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -f docker/docker-compose.yml up -d --build --wait auth-service
```

## Suite de Auth

```powershell
docker compose -f docker/docker-compose.yml run --rm --no-deps -T -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=admin1234 -e DJANGO_PRIVATE_KEY_PATH=/tmp/auth-test/private.pem -e DJANGO_PUBLIC_KEY_PATH=/tmp/auth-test/public.pem auth-service python manage.py test users core --noinput
```

El operador de la base local crea una base de pruebas separada. Las claves de prueba se guardan en el contenedor efímero. La suite cubre los límites de identidad, relaciones multiempresa, JWT y contraseñas, el límite concurrente de login y la configuración.

## Esquema y permisos

```powershell
docker compose -f docker/docker-compose.yml exec -T auth-service python manage.py spectacular --validate --file /tmp/auth-openapi.yaml
Get-Content -Raw scripts/database/auth/verify_roles.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
```

La prueba SQL revierte la tabla de verificación del rol de migración y comprueba que el rol web carece de DDL permanente y de acceso directo a documentos. CI también ejecuta la prueba sobre una instalación nueva. La validación de OpenAPI puede emitir avisos sobre parámetros o tipos inferidos. Revisa cualquier error nuevo y la presencia de las rutas que cambiaste.

## Dependencias e imagen

Reconstruye la imagen con `docker compose -f docker/docker-compose.yml build --pull auth-service`. CI verifica dependencias instaladas con `python -m pip check`. En un entorno de herramientas separado, consulta avisos con `pip-audit --disable-pip --no-deps -r backend/AuthServices/requirements.txt`.

Para auditar también el sistema base, exporta `docker-auth-service` con `docker image save` a un archivo temporal y usa `trivy image --input <archivo> --scanners vuln --severity HIGH,CRITICAL`. Registra el identificador de imagen, los hallazgos de Debian y de Python y las versiones corregidas disponibles. La última evidencia está en el [tablero](../MODERNIZATION.md).
