# DocumentLibraryServices

Organiza carpetas, favoritos y documentos recientes dentro de la biblioteca autorizada.

## Recorrido

```mermaid
flowchart LR
    client["Navegación y organización"] --> service["Biblioteca y jerarquía de carpetas"] --> storage["PostgreSQL y funciones acotadas"]
```

## Arranque local

Configura el entorno según el [README del proyecto](../../README.md#probar-en-local) y ejecuta desde la raíz.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait document-library-service
```

Puerto local **8006**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#contrato-http-actual).
- [Operación y configuración](docs/REFERENCE.md#arranque-y-permisos).
- [Pruebas y evidencia](docs/REFERENCE.md#pruebas).
- [Instrucciones del componente](AGENTS.md) y [skill documental-library](../../.agents/skills/documental-library/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
