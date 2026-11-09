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

La prueba SQL revierte la tabla de verificación del rol de migración y comprueba que el rol web carece de DDL permanente y de acceso directo a documentos. CI también ejecuta la prueba sobre una instalación nueva. La validación de OpenAPI terminó sin errores en la revisión de cierre. Mantiene cinco avisos distintos de inferencia de identificadores multiempresa, que el esquema representa como cadenas.

## Dependencias e imagen

Reconstruye la imagen con `docker compose -f docker/docker-compose.yml build --pull auth-service`. CI verifica dependencias instaladas con `python -m pip check`. En un entorno de herramientas separado, consulta avisos con `pip-audit --disable-pip --no-deps -r backend/AuthServices/requirements.txt`.

Para auditar también el sistema base, exporta `docker-auth-service` con `docker image save` a un archivo temporal y usa `trivy image --input <archivo> --scanners vuln --severity HIGH,CRITICAL`. Registra el identificador de imagen, los hallazgos de Debian y de Python y las versiones corregidas disponibles.

La auditoría del 3 de noviembre de 2026 no encontró avisos con `pip-audit` en las versiones fijadas. Trivy 0.74.0 encontró cero avisos altos o críticos en Python y nueve CVE altos sin corrección indicada en Debian 13. El digest y el detalle del alcance quedaron en el [PR de auditoría](https://github.com/Blandskron/AgenteIADocumental/pull/13). Es evidencia de esa imagen y de las bases de avisos consultadas en esa fecha.

## Jerarquía compartida — PLAT-001C

La prueba `scripts/database/tests/test_tenant_hierarchy.py` se ejecuta desde la imagen Auth contra una DB desechable `plat_hierarchy_*`, después del bootstrap y de `migrations/005_tenant_hierarchy.sql`. Requiere `POSTGRES_DB` y `PLAT_TEST_DATABASE` con ese nombre, `PLAT_TEST_ADMIN_PASSWORD` de prueba y las credenciales de ejemplo de `auth_runtime`. Copiar la prueba y `constraints/004_tenant_hierarchy.sql` a `/tmp/test_tenant_hierarchy.py` y `/tmp/tenant-hierarchy.sql`; ejecutar `python /tmp/test_tenant_hierarchy.py`. CI prepara y retira esa DB automáticamente.

Comprueba movimientos válidos, ciclos propios/descendientes/multifila, padres de otra empresa o ausentes, identidad inmutable, conservación documental, repetibilidad y deriva. Usa logins reales, observa esperas de PostgreSQL y enfrenta movimientos opuestos en Read Committed, Repeatable Read y Serializable, también tras rollback. Verifica HTTP 409 sin datos SQL y reutilización de conexión; las fixtures corruptas nunca salen de su transacción. Esta prueba no activa la migración en el stack general ni cierra el ciclo de vida de usuarios pendiente.

## Ciclo de vida de membresías — PLAT-001C2

`scripts/database/tests/test_tenant_user_links.py` exige una DB sintética `plat_identity_*` compartida por `POSTGRES_DB` y `PLAT_TEST_DATABASE`. Inicializarla con run_all.sql, provision_roles.sql y las migraciones reales de Django/grant_auth_runtime, usando auth_migrate. Aplicar la migración 006 como operador; copiar el cuerpo `constraints/005_tenant_user_links.sql` a `/tmp/tenant-user-links.sql` y la prueba a `/tmp/test_tenant_user_links.py` en Auth. Ejecutar con auth_runtime, `PLAT_TEST_ADMIN_PASSWORD` sintética y `python /tmp/test_tenant_user_links.py`. El paso de CI prepara y retira esa DB, y repite bootstrap, provisión, migraciones y activación.

Son 18 pruebas con logins reales: creación canónica, rechazo/override, primera activación con datos, baja SQL/HTTP, suspensión, secuencia normal sin reutilización, conservación documental, carreras insert/delete en ambos órdenes y rollback con bloqueo observado, 409 tras validar, sesión Auth rechazada tras baja, repetibilidad, deriva y rollback completo. Las fixtures huérfanas/no canónicas nunca se confirman. La suite general de Auth añade validación HTTP de referencias canónicas y suma 40 pruebas. No se usan claves ni cuentas de la instalación personal.
