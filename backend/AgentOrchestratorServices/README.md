# AgentOrchestratorServices

Servicio opcional de orquestación agéntica (ver [ADR-006](../../docs/ADR_AGENT_ORCHESTRATOR.md) y [ADR-007](../../docs/ADR_CODE_MODE_SANDBOX.md)), deshabilitado por defecto (`AGENTS_ENABLED=false`) para mantener intacto el despliegue base de Docker Compose.

## Arranque opcional

```bash
# Modo 2 — Agente documental multi-paso
AGENTS_ENABLED=true STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml -f docker/compose/agents.yml --profile studio --profile agents up -d --build

# Modo 3 — Agente + Code Mode en sandbox endurecido (Deno --deny-all)
AGENTS_ENABLED=true CODE_MODE_ENABLED=true STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml -f docker/compose/agents.yml -f docker/compose/code-mode.yml --profile studio --profile agents --profile code-mode up -d --build
```

Puerto local **8019**.

## Endpoints principales

- `GET /api/v1/health`: estado del servicio y banderas `agents_enabled` / `code_mode_enabled`.
- `GET /api/v1/agents/tools`, `/tools/search` y `/tools/{tool_name}`: catálogo allowlisted y descubrimiento progresivo estrictamente `read_only=True` (MCP + `DocumentSearchServices` + `DocumentAccessServices`, requiere JWT RS256 + verificación vigente en `AuthServices /api/users/me/`).
- `GET /api/v1/agents/templates`: plantillas especializadas (`research_general`, `contract_comparison`, `dates_amounts_extraction`, `executive_report_studio`).
- `GET /api/v1/agents/quota` y `GET /api/v1/agents/metrics`: cuota diaria y telemetría no sensible por tenant.
- `POST /api/v1/agents/runs`: inicia una ejecución idempotente (`mode: agent | code_mode`, `template_id`, `idempotency_key`, rate-limit deslizante + cuotas diarias).
- `GET /api/v1/agents/runs`, `GET /api/v1/agents/runs/{run_id}` y `GET /api/v1/agents/runs/{run_id}/checkpoints`: historial, detalle y metadatos de checkpoints estrictamente aislados por `(tenant_id, user_id)`.
- `GET /api/v1/agents/runs/{run_id}/stream`: flujo SSE de pasos, aprobación y estado final.
- `POST /api/v1/agents/runs/{run_id}/analyze`: análisis determinista de fechas, vencimientos, montos y comparativa de cláusulas sin coste extra de LLM.
- `GET /api/v1/agents/runs/{run_id}/export?format=markdown|csv` y `POST /api/v1/agents/runs/{run_id}/export-pdf`: exportación directa Markdown/CSV seguro y handoff PDF hacia `DocumentExportServices`.
- `POST /api/v1/agents/runs/{run_id}/resume`: aprobación o rechazo humano explícito (Human-in-the-Loop) con handoff a Knowledge Studio.
- `POST /api/v1/agents/runs/{run_id}/cancel`: cancelación cooperativa verificada antes de cada nodo y herramienta.

## Arquitectura interna

- `app/config/security.py`: validación JWT RS256 usando la clave pública de `AuthServices`.
- `app/application/tools/registry.py` y `app/infrastructure/mcp/mcp_client.py`: catálogo tipado de solo lectura y cliente MCP JSON-RPC 2.0 con propagación JWT.
- `app/infrastructure/llm/model_factory.py`: resolución dinámica Groq / Ollama / OpenAI-compatible desde `tenant_integrations`, protección SSRF, descifrado `secrets1.` y fallback JSON estructurado para modelos Ollama pequeños.
- `app/application/graph/`: grafo principal (`research_graph.py`), aprobación humana (`approval_node.py`) y nodo opcional Code Mode (`code_mode_node.py`).
- `app/infrastructure/database/`: checkpoints estrictos (`LANGGRAPH_STRICT_MSGPACK=true`), repositorio de runs/aprobaciones y auditoría saneada en `public.audit_logs`.
- `app/infrastructure/sandbox/sandbox_client.py` y `app/infrastructure/studio/studio_client.py`: RPC interno sin credenciales hacia `code-sandbox-runner` y handoff verificado hacia Knowledge Studio.
