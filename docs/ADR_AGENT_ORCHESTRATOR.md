# ADR-006 — Orquestación Agéntica Opcional (`AgentOrchestratorServices` y Máquina de Estados con Checkpointing)

**Estado:** Implementado (`AGENTS_ENABLED=false` por defecto)  
**Fecha:** 2026-11-21 (actualizado 2026-11-23 en `EVO-004`)  
**Ámbito:** `backend/AgentOrchestratorServices/`, `scripts/database/schemas/014_agent_orchestrator.sql`, `docker/compose/agents.yml`, `frontend/`

---

## 1. Contexto

El chat documental actual (`RagDocumentChatServices`) resuelve consultas *single-turn* con recuperación híbrida (`pgvector` HNSW + FTS + RRF) y citas verificables `[Fuente N]`. Para tareas documentales multi-etapa (investigación entre varios documentos, comparación de contratos, detección de vencimientos, flujos con aprobación humana y reanudación tras reinicios) se requiere orquestación con estado persistente sin comprometer el RAG base ni el arranque en 1 comando de Docker Compose.

## 2. Decisión

1. **Servicio opcional independiente (`backend/AgentOrchestratorServices/`, puerto `8019`):**
   - Deshabilitado por defecto (`AGENTS_ENABLED=false`) y aislado en el overlay `docker/compose/agents.yml` (`--profile agents`).
   - El stack base (`docker compose up -d --build`) no construye, no instala ni arranca dependencias agénticas.
2. **Máquina de estados determinista en Python puro con checkpointing PostgreSQL:**
   - La orquestación se implementa directamente en `app/application/graph/research_graph.py` (`ResearchAgentGraph`) sin dependencias de runtime de `langgraph` ni `langchain-core`, lo que reduce la superficie de dependencias, el consumo de RAM y la latencia en despliegues local-first.
   - Los checkpoints se serializan en JSON estricto (`state_format = 'strict_json'`) dentro de `agents.agent_checkpoints` mediante `PostgresAgentCheckpointer`, con soporte para cancelación cooperativa, pausa en `WAITING_APPROVAL` y reanudación humana (`POST /api/v1/agents/runs/{run_id}/resume`).
   - El router LLM reutiliza la configuración dinámica Groq / Ollama local del tenant (`public.tenant_integrations`), con fallback JSON estructurado para modelos Ollama pequeños (`2b`/`3b`).
3. **Aislamiento estricto de datos y privilegios:**
   - Nuevo esquema PostgreSQL `agents.*` con rol dedicado `agent_runtime` sin permisos sobre `public.documents`, `public.document_embeddings` ni archivos originales.
   - Toda consulta documental pasa por HTTP/MCP propagando el JWT RS256 del usuario; cada microservicio destino sigue siendo la autoridad de autorización.
   - Cuotas diarias de tokens, tope de pasos (`max_steps` acotado) y auditoría obligatoria en `public.audit_logs` (`SELECT, INSERT` para `agent_runtime`).

## 3. Criterios de descarte / rollback

- Desactivar `AGENTS_ENABLED=false` o retirar el perfil `--profile agents` restaura el sistema al 100 % sin tocar tablas de `public.*` ni el Chat RAG tradicional.
- Si los modelos Ollama pequeños (`2b`/`3b`) fallan en *native tool calling*, el adaptador usa fallback JSON estructurado en lugar de exigir llamadas nativas.

