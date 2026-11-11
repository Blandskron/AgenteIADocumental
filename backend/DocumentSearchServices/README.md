# DocumentSearchServices

Expone búsqueda, detalle y selección de documentos visibles para la identidad vigente.

## Recorrido

```mermaid
flowchart LR
    client["Navegador"] --> service["Autorización y filtros documentales"] --> storage["Consultas PostgreSQL de solo lectura"]
```

## Arranque local

Configura el entorno según el [README del proyecto](../../README.md#probar-en-local) y ejecuta desde la raíz.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait document-search-service
```

Puerto local **8004**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#api-endpoints).
- [Operación y configuración](docs/REFERENCE.md#running-the-service).
- [Pruebas y evidencia](docs/REFERENCE.md#verificación-de-la-imagen).
- [Instrucciones del componente](AGENTS.md) y [skill documental-search](../../.agents/skills/documental-search/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
