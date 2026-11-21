# DocumentTransferServices

Registra el historial privado de cargas y descargas que comunica la web.

## Recorrido

```mermaid
flowchart LR
    client["Flujo de carga o descarga web"] --> service["Diario de transferencias"] --> storage["Eventos privados en PostgreSQL"]
```

## Arranque local

Ejecuta desde la raíz del proyecto (ver [instalación rápida](../../README.md#instalación-rápida-1-comando)):

```bash
docker compose up -d --build --wait document-transfer-service
```

Puerto local **8007**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#contrato-http).
- [Operación y configuración](docs/REFERENCE.md#operación).
- [Pruebas y evidencia](docs/REFERENCE.md#validación-y-límites-de-la-evidencia).
- [Instrucciones del componente](AGENTS.md) y [skill documental-transfer](../../.agents/skills/documental-transfer/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
