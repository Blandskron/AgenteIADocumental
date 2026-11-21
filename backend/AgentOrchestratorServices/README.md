# AgentOrchestratorServices

Servicio opcional de orquestación agéntica (ver [ADR-006](../../docs/ADR_AGENT_ORCHESTRATOR.md) y [ROADMAP.md](../../ROADMAP.md)), deshabilitado por defecto (`AGENTS_ENABLED=false`) para mantener intacto el despliegue base de Docker Compose.

## Arranque opcional

```bash
AGENTS_ENABLED=true STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml -f docker/compose/agents.yml --profile studio --profile agents up -d --build
```

Puerto local **8019**.

## Componentes actuales (Fase 1)

- `app/config/security.py`: validación JWT RS256 usando la clave pública de `AuthServices`.
- `app/application/tools/registry.py`: catálogo tipado de herramientas de solo lectura con política de capacidades, tope de resultados (`<= 20`) y redacción de secretos.
- `app/infrastructure/mcp/mcp_client.py`: adaptador cliente MCP JSON-RPC 2.0 que propaga el JWT del usuario hacia `KnowledgeStudioServices /api/v1/mcp`.
- `app/main.py`: entrypoint FastAPI acotado por `AGENTS_ENABLED`.

