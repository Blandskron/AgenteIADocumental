# AuthServices

AuthServices autentica usuarios y emite JWT RS256 para el frontend y los servicios documentales de Blandskron. También administra identidades globales y membresías de empresa mediante Django REST Framework.

## Arranque local

Desde la raíz del repositorio:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -f docker/docker-compose.yml up -d --build --wait auth-service
docker compose -f docker/docker-compose.yml exec auth-service python manage.py createsuperuser
```

Crea el administrador solo en el primer arranque. Abre [Django Admin](http://localhost:8001/admin/) o [Swagger](http://localhost:8001/docs/api/schema/swagger-ui/). Para probar el flujo documental completo, sigue el [README raíz](../../README.md).

## Guías

- [Contrato de API](docs/API.md) para sesión, perfil, claims y administración.
- [Operación y configuración](docs/OPERATIONS.md) para arranque, migraciones, roles de base, secretos, rotación y auditoría.
- [Pruebas](docs/TESTS.md) para la suite de Auth, OpenAPI, permisos de PostgreSQL y revisión de dependencias.
- [AGENTS.md](AGENTS.md) para colaborar y [tablero del repositorio](../../ROADMAP.md) para seguimientos.

Las rutas y serializadores viven en `users/`. Las rutas de Swagger, ReDoc y OpenAPI están en [core/openapi.py](core/openapi.py). `docs/` contiene las guías escritas. Django gestiona las tablas de identidad y sesión. El esquema multiempresa vive en [scripts/database](../../scripts/database/) y se mapea con modelos no gestionados.

El seguimiento de integridad compartida PLAT-001 dispone de un [preflight y mapa de escritores](../../scripts/database/README.md). Incluye diagnóstico de solo lectura y migraciones optativas validadas con carreras SQL. La activación general y el cierre del ciclo de vida conservan sus tarjetas; los conflictos HTTP conocidos se describen en la guía de API.

La migración optativa 006 añade el ciclo de vida de membresías: se ejecuta después de las migraciones Django, conserva el `user_id` textual y elimina membresías/asignaciones al borrar la cuenta, manteniendo documentos históricos. Deshabilitar conserva la configuración. Consulta la [operación SQL](../../scripts/database/README.md#identidad-auth-y-membresías--segundo-incremento-plat-001c) antes de aplicarla; todavía no se activa automáticamente en Compose.
