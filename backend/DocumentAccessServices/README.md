# DocumentAccessServices

Entrega contenido y originales autorizados y coordina el borrado documental.

## Recorrido

```mermaid
flowchart LR
    web["Vista previa, descarga o borrado"] --> access["API de acceso"]
    access --> auth["Auth e identidad vigente"]
    access -->|"Permisos y referencias"| db[("PostgreSQL")]
    access -->|"Leer o retirar original"| volume[("Volumen documental")]
```

## Arranque local

Configura el entorno según el [README del proyecto](../../README.md#probar-en-local) y ejecuta desde la raíz.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait document-access-service
```

Puerto local **8005**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#api-endpoints).
- [Operación y configuración](docs/REFERENCE.md#running-the-service).
- [Pruebas y evidencia](docs/REFERENCE.md#pruebas).
- [Instrucciones del componente](AGENTS.md) y [skill documental-access](../../.agents/skills/documental-access/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
