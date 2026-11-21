# ADR-006 — Orquestación Agéntica Opcional (`AgentOrchestratorServices`, LangGraph y `langchain-core`)

**Estado:** Aprobado para implementación incremental  
**Fecha:** 2026-11-21  
**Ámbito:** `backend/AgentOrchestratorServices/`, `scripts/database/schemas/014_agent_orchestrator.sql`, `docker/compose/agents.yml`, `frontend/`

---

## 1. Contexto

El chat documental actual (`RagDocumentChatServices`) resuelve consultas *single-turn* con recuperación híbrida (`pgvector` HNSW + FTS + RRF) y citas verificables `[Fuente N]`. Para tareas documentales multi-etapa (investigación entre varios documentos, comparación de contratos, detección de vencimientos, flujos con aprobación humana y reanudación tras reinicios) se requiere orquestación con estado persistente sin comprometer el RAG base ni el arranque en 1 comando de Docker Compose.

## 2. Decisión

1. **Servicio opcional independiente (`backend/AgentOrchestratorServices/`, puerto `8019`):**
   - Deshabilitado por defecto (`AGENTS_ENABLED=false`) y aislado en el overlay `docker/compose/agents.yml` (`--profile agents`).
   - El stack base (`docker compose up -d --build`) no construye, no instala ni arranca dependencias agénticas.
2. **Orquestación con LangGraph + uso mínimo de `langchain-core`:**
   - Se adopta `langgraph` + `langgraph-checkpoint-postgres` (`LANGGRAPH_STRICT_MSGPACK=true`) para `StateGraph`, checkpoints persistentes, cancelación cooperativa e `interrupt()` / `Command(resume=...)` para Human-in-the-Loop.
   - De LangChain se adopta únicamente el núcleo mínimo (`langchain-core`, `langchain-mcp-adapters` y wrappers ligeros de chat) reutilizando el router dinámico Groq / Ollama local del tenant. **No** se adoptan loaders, splitters, retrievers ni vectorstores de LangChain.
3. **Aislamiento estricto de datos y privilegios:**
   - Nuevo esquema PostgreSQL `agents.*` con rol dedicado `agent_runtime` sin permisos sobre `public.documents`, `public.document_embeddings` ni archivos originales.
   - Toda consulta documental pasa por HTTP/MCP propagando el JWT RS256 del usuario; cada microservicio destino sigue siendo la autoridad de autorización.
   - Cuotas diarias de tokens, tope de pasos (`recursion_limit`) y auditoría obligatoria en `public.audit_logs`.

## 3. Criterios de descarte / rollback

- Desactivar `AGENTS_ENABLED=false` o retirar el perfil `--profile agents` restaura el sistema al 100 % sin tocar tablas de `public.*` ni el Chat RAG tradicional.
- Si los modelos Ollama pequeños (`2b`/`3b`) fallan en *native tool calling*, el adaptador usa fallback JSON estructurado en lugar de exigir llamadas nativas.

