# 07 — Auditoría de `KnowledgeStudioServices`, `AgentOrchestratorServices`, `CodeSandboxRunner` y MCP

- **Propósito:** Cumplir la revalidación obligatoria de la Etapa IV (secciones 7.1 a 7.4) sobre las capacidades evolucionadas recientemente en `develop@5a4fac2` (22 de noviembre de 2026).
- **Método:** Inspección directa línea por línea del código fuente, esquemas SQL (`013_knowledge_studio.sql`, `014_agent_orchestrator.sql`), roles de BD, ADRs (`ADR-005`, `ADR-006`, `ADR-007`), overlays Docker Compose y ejecución de las suites pytest locales.

---

## 1. Auditoría de `KnowledgeStudioServices` (Sección 7.1)

**Resultado de pruebas locales:** `11 passed, 1 skipped` (0.18s) + `run_studio_eval_gate.py` (`passed=True`). **Cobertura real contra PostgreSQL: 0 %** (todos los tests usan repositorios y generadores mock).

| Capacidad auditada | Estado real | Evidencia en código | Hallazgos y brechas |
|---|---|---|---|
| **Plantillas y familias de artefactos** | `IMPLEMENTADO PARCIALMENTE` | `app/domain/artifacts.py` (`P0_TEMPLATES`: 12 IDs) | Solo es un `set` de 12 strings que comparten un único esquema `ArtifactContent`; **no existen prompts ni generadores diferenciados por plantilla**. |
| **Generación de informes** | `IMPLEMENTADO PARCIALMENTE` | `app/application/studio_runner.py` (`execute_studio_job`) | Recibe callback `generate_json` inyectado, pero **no existe ningún cliente LLM (Ollama/Groq) instalado ni implementado** en `requirements.txt` ni en el servicio. |
| **Matrices de evidencia y validación de fuentes** | `IMPLEMENTADO Y VERIFICADO` (con bug borde) | `validate_groundedness()` (`artifacts.py:91-147`), `POST /studio/validate` | Valida normalización de `quote_text` contra `chunk_lookup` y `status=="proposed"`. **Bug:** si `claims == []`, devuelve `score=1.0, valid=True`. |
| **Exportación** | `IMPLEMENTADO PARCIALMENTE` | `render_evidence_table_csv()` (`POST /studio/export-csv`) | CSV con neutralización de formula injection (`=`, `+`, `-`, `@`). **Sin exportación MD ni PDF** en el servicio. |
| **Colecciones** | `IMPLEMENTADO PARCIALMENTE` | `013_knowledge_studio.sql`, `StudioRepositoryPg` | Existe tabla `studio.collection_documents`, pero **no hay endpoints ni métodos** para asociar documentos a colecciones. |
| **Artefactos versionados** | `IMPLEMENTADO PARCIALMENTE` (**ROTO EN PG REAL**) | `studio_repository_pg.py:216-280` vs `013_knowledge_studio.sql` | **BUG CRÍTICO:** `save_artifact()`, `list_artifacts()` y `get_artifact()` consultan/insertan columnas `content`, `version` y `groundedness_score` directamente en `studio.artifacts` (que **no existen** en SQL) e **ignoran completamente `studio.artifact_versions`**. |
| **Mapas conceptuales y gráficos deterministas** | `IMPLEMENTADO PARCIALMENTE` | `visuals_and_learning.py` (`build_concept_graph_from_wikilinks`, `extract_verified_chart_series`, `sanitize_mermaid_diagram`) | Funciones puras y endpoints existen, pero no leen de PostgreSQL ni están conectados a `StudioPage.tsx` (Mermaid solo valida regex, no renderiza SVG). |
| **Cuestionarios y repetición espaciada SM-2** | `IMPLEMENTADO PARCIALMENTE` | `filter_valid_quiz_questions`, `sm2_review` (`POST /studio/flashcards/review`) | `QuizQuestion` no tiene endpoint ni generador; `sm2_review` es **stateless** (no persiste progreso en PostgreSQL). |
| **Cuotas** | `IMPLEMENTADO PARCIALMENTE` | `app/application/quota_guard.py` (`StudioQuotaGuard`) | Vive solo en memoria y **no está instanciado ni conectado en `app/main.py`**. |
| **Ejecución asíncrona** | `IMPLEMENTADO PARCIALMENTE` | `app/interfaces/worker.py` (`StudioWorker.run_once`) | No tiene loop daemon, no llama a `save_artifact()`, no está en `docker/compose/studio.yml`: los jobs en `POST /studio/jobs` quedan `PENDING` indefinidamente. |
| **Pool DB y seguridad HTTP** | **BRECHA CRÍTICA** | `app/main.py:62-70` y rutas utilitarias | `_get_studio_repo()` crea un `create_engine()` nuevo en cada request (fuga de conexiones). 7 endpoints utilitarios carecen de `Depends(require_studio_user)`. `require_studio_user` no valida vigencia en vivo contra Auth. |

**Conclusión 7.1:** **No crear otro módulo de investigación.** El esquema SQL (`013_knowledge_studio.sql`), el trigger `STALE` cross-schema, el dominio de validación y el componente visual ya existen; la prioridad es reparar `StudioRepositoryPg`, conectar el cliente LLM/worker y cablear `StudioPage.tsx`.

---

## 2. Auditoría de `AgentOrchestratorServices` (Sección 7.2)

**Resultado de pruebas locales:** `36 passed, 2 skipped` (0.51s) + `check_agents_contract.py` (`PASS`). **Cobertura real contra PostgreSQL y servicios HTTP: 0 %.**

| Capacidad auditada | Estado real | Evidencia en código | Hallazgos y brechas |
|---|---|---|---|
| **Uso de LangGraph** | **`DOCUMENTADO`** (no implementado) | `ADR_AGENT_ORCHESTRATOR.md` vs `requirements.txt` y `research_graph.py` | **Discrepancia directa:** `langgraph`, `langgraph-checkpoint-postgres`, `langchain-core` y `langchain-mcp-adapters` **NO existen** en `requirements.txt` ni en el código. `ResearchAgentGraph` es una máquina de estados propia en Python puro; `LANGGRAPH_STRICT_MSGPACK` solo activa validación `strict_json` en JSONB. |
| **Persistencia PostgreSQL (`agent_runs`)** | `IMPLEMENTADO PARCIALMENTE` (**ROTO EN PG REAL**) | `runs_repository.py:235-269` vs `014_agent_orchestrator.sql` | `update_run()` descarta silenciosamente `pending_approval`, `code_executions` y `studio_handoff` (columnas inexistentes en `agents.agent_runs`); `get_run()` no consulta `agents.agent_approvals`. Fuga de `create_engine()` por request en `runs_routes.py:101-130`. |
| **Checkpoints y reanudación** | `IMPLEMENTADO PARCIALMENTE` | `checkpointer.py`, `runs_routes.py:320` | Guarda checkpoints compactados tras cada paso, pero `prune_old_checkpoints()` nunca se invoca en producción y `POST /resume` solo resuelve aprobación HITL sin reanudar pasos del grafo tras fallo. |
| **Auditoría (`public.audit_logs`)** | `IMPLEMENTADO PARCIALMENTE` (**ROTO EN PG REAL**) | `audit_logger.py:65-98` vs `011_notifications_audit.sql`, `agents/provision_role.sql:39` | Usa columnas `id`, `target_type`, `target_id` (las reales son `audit_id`, `resource_type`, `resource_id`) y `agent_runtime` **no tiene `SELECT`** en `public.audit_logs`. Errores silenciados con `except Exception`. |
| **Identidad en vivo y Docker Compose** | **ROTO EN COMPOSE** | `docker/compose/agents.yml:41` | `AUTH_IDENTITY_URL` apunta a `http://auth-service:8000/api/users/me/` cuando `auth-service` escucha en el puerto **`8001`**. |
| **Cliente MCP y herramientas autorizadas** | `IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL` | `mcp_client.py`, `search_client.py`, `access_client.py`, `ToolRegistry` | Allowlist read-only estricta (4 tools MCP + `search_documents_fts` + `get_document_metadata` + `execute_code` condicional). **Carece de herramienta RAG semántica/vectorial** (solo FTS/ILIKE). Descubrimiento progresivo solo existe en HTTP, no en el bucle LLM. |
| **Plantillas y analizadores deterministas** | `IMPLEMENTADO PARCIALMENTE` | `agent_templates.py`, `contract_comparator.py`, `expiration_detector.py`, `risk_assessor.py` | 4 plantillas y 4 analizadores probados unitariamente, pero `/analyze` opera solo sobre snippets de 300 chars de `run["sources"]`. |
| **Handoff a Knowledge Studio** | **ROTO EN INTEGRACIÓN REAL** | `approval_node.py:98`, `studio_client.py` | Envía `template_id="executive_brief"` (inválido en `P0_TEMPLATES`) y JSON `content` incompatible con `ArtifactContent` (HTTP 400/422 en real; siempre cae al fallback MD/CSV). |
| **Exportación (MD, CSV, PDF)** | `IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL` | `export_service.py`, `pdf_export_client.py` | MD y CSV locales con neutralización de fórmulas; **bug de ruta en PDF:** `pdf_export_client.py` llama a `/api/v1/exports/chat-snapshot`, mientras `DocumentExportServices` expone `/api/v1/exports/chat-message/pdf`. |
| **HITL, cancelación y `/retry`** | `IMPLEMENTADO PARCIALMENTE` | `approval_node.py`, `runs_routes.py` | HITL usa `FOR UPDATE` (409 en doble decisión), pero `pending_approval` se pierde en PG real; cancelación no aborta HTTP LLM en curso; `/retry` no preserva `template_id`, `save_to_studio`, `max_steps` ni `max_tokens`. |
| **Ejecución asíncrona y SSE** | `IMPLEMENTADO PARCIALMENTE` | `runs_routes.py` | `POST /agents/runs` ejecuta el grafo síncronamente; `GET /stream` solo vuelca pasos ya persistidos (no streaming real). |
| **Límites, cuotas y anti-inyección** | `IMPLEMENTADO PARCIALMENTE` | `rate_limiter.py`, `concurrency_guard.py`, `quota_service.py`, `prompt_guard.py` | Cuotas diarias en PG; rate limit/concurrencia en memoria. **Brechas:** `state["goal"]` usa el `goal` sin sanitizar (`research_graph.py:187,213`); `detect_prompt_injection_patterns()` nunca se invoca en runtime. |
| **Modelos locales pequeños (Ollama)** | `IMPLEMENTADO PARCIALMENTE` | `model_factory.py`, `research_graph.py:287-292` | Tiene `parse_structured_json_fallback()`, pero **`system_prompt` nunca explica el formato JSON de fallback**, por lo que modelos 2B–3B que no emiten `tool_calls` nativos terminan devolviendo texto plano sin usar herramientas. |

**Recomendación sobre LangGraph vs máquina de estados propia:** Antes de añadir `langgraph` + `langchain-core` (que introducen un grafo grande de dependencias y ciclos rápidos de cambios), conviene **mantener la máquina de estados ligera en Python puro**, completar su persistencia/reanudación real en PostgreSQL y **actualizar `ADR_AGENT_ORCHESTRATOR.md`** para reflejar fielmente la implementación real.

---

## 3. Auditoría de `CodeSandboxRunner` (Sección 7.3)

**Resultado de pruebas locales:** `3 passed, 1 skipped` (0.11s). El test live de Deno se omitió por no estar `deno` en el host Windows.

### Fortalezas verificadas
- **Aislamiento de proceso:** Subproceso Deno efímero por ejecución con `--deny-all --no-remote --no-npm --no-prompt --v8-flags=--max-old-space-size=128`, `clearEnv: true`, `stdin: "null"` y `SIGKILL` tras `CODE_SANDBOX_TIMEOUT_MS` (5000 ms, máximo 10000 ms).
- **Aislamiento de red y contenedor:** Red Docker `code_sandbox_net` con `internal: true`, sin `ports`, sin `volumes`, `read_only: true`, `cap_drop: ["ALL"]`, `no-new-privileges:true`, `mem_limit: 256m`, `cpus: 0.5`, `pids_limit: 64`, `/tmp` `tmpfs` de 16 MiB (`noexec,nosuid,nodev`).
- **Ausencia de secretos:** No recibe `DATABASE_URL`, JWT ni API keys; `SandboxHttpClient` purga claves sensibles (`strip_credentials_from_data`) antes de enviar `evidence`.
- **Sin `eval`/`new Function`/`node:vm`** en el proceso coordinador `server.ts`.

### Limitaciones reales a corregir (sin sustituir el sandbox)
1. **Sin autenticación en `POST /execute`:** Añadir un secreto interno compartido por entorno entre `AgentOrchestratorServices` y `CodeSandboxRunner` para evitar invocaciones no autorizadas desde la red interna.
2. **Sin límite de concurrencia interno en `server.ts`:** Añadir semáforo (p. ej. máx. 2–4 subprocesos simultáneos) para prevenir agotamiento de `pids_limit: 64` o de los 16 MiB de `/tmp`.
3. **Delimitador de salida en stdout:** Si el script imprime `__CM_RESULT__` varias veces, el último gana; usar un marcador único por ejecución (nonce) o archivo temporal de salida.
4. **Pruebas adversariales en CI:** Ejecutar `test_live_deno_deny_all_blocks_fs_env_and_network` dentro del contenedor Deno en `ci-integration.yml` añadiendo casos de bucle infinito (timeout), bomba de memoria (OOM 128 MB) y ofuscación `globalThis["Deno"]`.
5. **Discrepancia menor con `ADR_CODE_MODE_SANDBOX.md`:** El ADR menciona un canal RPC tipado hacia el host que no existe; el modelo actual (datos puros entrada → JSON salida) es **más seguro** y debe conservarse, actualizando el ADR.

**Conclusión 7.3:** **No sustituir `CodeSandboxRunner` por ningún servicio externo.** Su arquitectura local con Deno `--deny-all` es sólida y solo requiere endurecimiento incremental.

---

## 4. Auditoría del Servidor y Cliente MCP (Sección 7.4)

- **Protocolo y operación local:** JSON-RPC 2.0 sobre HTTP (`2024-11-05`) en `POST /api/v1/mcp` (`KnowledgeStudioServices`), 100 % local, con validación de header `Origin`.
- **Herramientas expuestas (4, estrictamente solo lectura):** `search_documents`, `get_document_chunks`, `list_studio_artifacts`, `get_studio_artifact` (`readOnlyHint: True`, `limit <= 20`).
- **Autenticación, aislamiento y auditoría:** Exige JWT RS256 válido (rechaza refresh tokens), filtra por `tenant_id` + `owner_user_id` / asignaciones activas, y escribe eventos `mcp.*` en `public.audit_logs`.
- **Brechas reales:**
  1. `list_studio_artifacts` y `get_studio_artifact` fallan en PostgreSQL real por el mismatch de columnas en `studio.artifacts`.
  2. `require_studio_user` valida firma JWT local pero **no verifica revocación/membresía en vivo** contra `AuthServices` (a diferencia de Library/Access/Search/Agents).
  3. **Falta 1 herramienta clave de solo lectura:** `search_documents_hybrid` (o `retrieve_rag_chunks`) para que el orquestador y clientes MCP autorizados accedan a la búsqueda híbrida HNSW+FTS+RRF y no solo a FTS/ILIKE.
- **¿Conviene ampliar la superficie MCP con escritura?:** **No en esta etapa.** Mantener MCP estrictamente en **solo lectura** (añadiendo únicamente recuperación híbrida y consulta de hallazgos/metadatos de solo lectura) protege la superficie multiempresa y preserva la aprobación humana explícita para cualquier mutación.
