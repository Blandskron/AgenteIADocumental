# ConversationServices

Persiste conversaciones y mensajes privados del chat documental y sus vínculos autorizados.

## Recorrido

```mermaid
flowchart LR
    client["Historial de chat web"] --> service["Conversaciones y mensajes del dueño"] --> storage["Persistencia PostgreSQL"]
```

## Arranque local

Configura el entorno según el [README del proyecto](../../README.md#probar-en-local) y ejecuta desde la raíz.

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --wait conversation-service
```

Puerto local **8008**.

## Guías

- [Contrato HTTP y autorización](docs/REFERENCE.md#api-endpoints).
- [Operación y configuración](docs/REFERENCE.md#running-the-service).
- [Pruebas y evidencia](../../docs/release/README.md).
- [Instrucciones del componente](AGENTS.md) y [skill documental-conversations](../../.agents/skills/documental-conversations/SKILL.md).
- [Mapa del backend](../README.md) y [verificación de entrega](../../docs/release/README.md).
