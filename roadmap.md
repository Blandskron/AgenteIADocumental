# Roadmap de Evolución — Blandskron Documental (Etapa 2) — COMPLETADO

> **Estado: 55 / 55 tareas terminadas (100 %).** Todas las fases planificadas (Fases 0–8: núcleo RAG híbrido, configuración web de IA, importación Markdown/ZIP, Knowledge Studio P0/P1 completo, persistencia SKIP LOCKED, worker, cuotas por tenant, hardening, auditoría, CI selectivo, visualizaciones deterministas y limpieza final) están implementadas y verificadas.

**Fecha de cierre de etapa:** 2026-11-21

---

## Resumen final de avance

| Fase | Enfoque | Total | Pendiente | En progreso | Terminada |
| --- | --- | ---: | ---: | ---: | ---: |
| **Fase 0** | Higiene técnica, historial único y base de evaluación | 4 | 0 | 0 | 4 |
| **Fase 1** | Configuración de IA (Groq) desde la web y degradación honesta | 5 | 0 | 0 | 5 |
| **Fase 2** | Motor RAG híbrido, búsqueda moderna y UX de chat | 5 | 0 | 0 | 5 |
| **Fase 3** | Ingesta idempotente y fuentes Markdown/ZIP (Opción O1) | 4 | 0 | 0 | 4 |
| **Fase 4** | Knowledge Studio P0 (artefactos con citas verificadas) | 6 | 0 | 0 | 6 |
| **Fase 5** | Hardening de seguridad y extensiones P1+ bajo demanda | 5 | 0 | 0 | 5 |
| **Fase 6** | Expansión operativa, visor de auditoría, OpenAI-compatible/Ollama, MCP y API Studio | 8 | 0 | 0 | 8 |
| **Fase 7** | Persistencia SKIP LOCKED, rol `studio_runtime`, cuotas, overlay Studio y Quiz UI | 8 | 0 | 0 | 8 |
| **Fase 8** | Cierre integral: limpieza `docs/plans`, CI Studio/eval, worker, factory LLM, cookie UI y exportación | 10 | 0 | 0 | 10 |
| **Total** | | **55** | **0** | **0** | **55** |

---

## Registro consolidado de entregas (`R0-01` – `R5-05`)

- **Fase 0 (`R0-01`–`R0-04`) — `terminada`:** Limpieza de planes, `Makefile` para 11 servicios, historial único `conversation_messages` y corpus sintético `S1`–`S5` (`scripts/eval/run_eval_baseline.py`).
- **Fase 1 (`R1-01`–`R1-05`) — `terminada`:** Migración `tenant_integrations` + roles mínimos, `SecretsCipher` (`secrets1.`), permiso `manage_ai_settings`, APIs DRF `/api/integrations/groq/*`, `GroqConfigResolver` dinámico con `provider_status` tipificado y vista web `/settings/ai`.
- **Fase 2 (`R2-01`–`R2-05`) — `terminada`:** Chunking estructural con `metadata.page`/`section`, índices `HNSW` + `content_tsv` GIN + trigram, recuperación híbrida `vector + FTS + RRF`, blindaje anti prompt-injection `<document_context>`, `SafeMarkdown` anti-XSS con citas `[Fuente N]` clicables y SSE opcional (`?stream=true`).
- **Fase 3 (`R3-01`–`R3-04`) — `terminada`:** Idempotencia por `Idempotency-Key` + `content_sha256`, extractor `MarkdownNormalizer`, endpoint seguro por lote `POST /api/v1/documents/import-batch` (anti zip-bomb/symlink/path-traversal) y tarjeta UI `Importar Markdown / ZIP` en `ApplicationsPage`.
- **Fase 4 (`R4-01`–`R4-06`) — `terminada`:** Esquema SQL aislado `studio.*` con trigger `FRESH -> STALE`, motor `KnowledgeStudioServices` (revalidación `ACCESS_REVOKED`, 4 familias P0, groundedness ≥ 95 %, CSV seguro), registro de renderers `studio_artifact` en `DocumentExportServices`, vista web `/studio` y gate `scripts/eval/run_studio_eval_gate.py`.
- **Fase 5 (`R5-01`–`R5-05`) — `terminada`:**
  - `R5-01`: Endpoints de sesión web `HttpOnly` + `SameSite=Lax` + CSRF (`/api/users/session/login|refresh|logout/`) en `AuthServices`.
  - `R5-02`: `AuditLog` persistente en `public.audit_logs` con redacción automática de claves sensibles y consulta paginada `GET /api/audit-logs/` con aislamiento por tenant (`auth_runtime` solo `SELECT`/`INSERT`).
  - `R5-03`: Visualizaciones deterministas en `KnowledgeStudioServices` (`sanitize_mermaid_diagram`, grafo desde `[[wikilinks]]`, series de gráficos exclusivamente desde celdas verificadas).
  - `R5-04`: Validador estricto de quizzes citados (`filter_valid_quiz_questions`) y motor SM-2 offline sin telemetría (`sm2_review`).
  - `R5-05`: ADR formal de extensibilidad OpenAI-compatible / Ollama / MCP de solo lectura ([docs/ADR_EXTENSIBILITY_LLM_MCP.md](docs/ADR_EXTENSIBILITY_LLM_MCP.md)).
- **Fase 6 (`R6-01`–`R6-08`) — `terminada`:**
  - `R6-01`: Integración de `record_audit_log()` persistente en las mutaciones de `ai_integrations.py` (sin exponer claves).
  - `R6-02`: Visor administrativo `/admin/audit` (`AuditLogsPage.tsx`, `audit-logs.api.ts`) con filtro por acción y enlace en `Sidebar`.
  - `R6-03`: Adaptador `OpenAICompatibleLLMProvider` con allowlist estricta anti-SSRF (`validate_provider_base_url`) y suite de pruebas.
  - `R6-04`: Entrypoint HTTP FastAPI en `KnowledgeStudioServices/app/main.py` acotado por `STUDIO_ENABLED` (templates, validación de groundedness, CSV, Mermaid, grafo, series verificadas y SM-2).
  - `R6-05`: Router `ReadOnlyMcpDispatcher` autenticado estrictamente con el usuario de la plataforma y auditoría `mcp.*`.
  - `R6-06`: Overlay opcional Docker Compose `docker/compose/ollama.yml` (`--profile local-llm`) sin alterar el stack base.
  - `R6-07`: Componente interactivo `OfflineFlashcardDeck` (SM-2 100 % local en el navegador) integrado en `/studio` + tests unitarios.
  - `R6-08`: Target `make eval-studio`, índice en `docs/maintainers.md` y validación integral.
- **Fase 7 (`R7-01`–`R7-08`) — `terminada`:**
  - `R7-01`: Repositorio PostgreSQL `StudioRepositoryPg` con cola atómica `FOR UPDATE SKIP LOCKED` e idempotencia por `(tenant_id, operation_key)`.
  - `R7-02`: Rol de privilegios mínimos `studio_runtime` (`scripts/database/studio/provision_role.sql` y `verify_role.sql`).
  - `R7-03`: `StudioQuotaGuard` (cuota diaria de tokens y límite de concurrencia por empresa con rollover diario + tests).
  - `R7-04`: Overlay Docker Compose opcional `docker/compose/studio.yml` (`--profile studio`) + `Dockerfile` (UID 10018, sin `pip`/`ensurepip`) y `requirements.txt` de `KnowledgeStudioServices`.
  - `R7-05`: Cliente HTTP frontend `studio.api.ts` + tests unitarios `studio.api.test.js`.
  - `R7-06`: Panel interactivo `InteractiveQuizPanel` (quizzes citados offline) integrado en `/studio`.
  - `R7-07`: Auditoría persistente `record_audit_log()` en pruebas de conexión Groq (`ai_settings_test`).
  - `R7-08`: Validación integral de todos los overlays Compose (`base`, `ollama.yml`, `studio.yml`), backend AST/tests y frontend (`128 / 128` tests + build).
- **Fase 8 (`R8-01`–`R8-10`) — `terminada`:**
  - `R8-01`: Retiro de planes ya ejecutados en `docs/plans/` y limpieza de enlaces en `docs/maintainers.md`.
  - `R8-02`: Actualización de `.env.example`, `README.md`, `backend/README.md`, `docs/operations.md` y `docs/maintainers.md` con Studio, Ollama y nuevas rutas web.
  - `R8-03`: Integración de `studio_eval` en `scripts/ci/detect_changes.py` y job rápido `studio-eval-fast` en `.github/workflows/ci-fast.yml` (conectado a `ci-fast-gate`).
  - `R8-04`: Adaptadores frontend de sesión Cookie `HttpOnly` + CSRF (`readCsrfToken`, `cookieLoginRequest`, `cookieRefreshRequest`, `cookieLogoutRequest`) + test unitario.
  - `R8-05`: Worker ejecutable `StudioWorker` (`backend/KnowledgeStudioServices/app/interfaces/worker.py`) acoplado a `SKIP LOCKED`, `StudioQuotaGuard` y `execute_studio_job` + tests.
  - `R8-06`: Panel `VerifiedVisualsPanel` (grafo conceptual SVG determinista + barras desde celdas verificadas con procedencia) integrado en `/studio` + test SSR.
  - `R8-07`: Exportación segura Markdown y CSV (con neutralización anti formula-injection y `URL.revokeObjectURL`) desde `/studio`.
  - `R8-08`: Factory unificada `build_llm_provider` (`groq`, `openai_compatible`, `ollama`) en `RagDocumentChatServices` + tests unitarios.
  - `R8-09`: Pruebas de humo HTTP FastAPI (`tests/test_studio_api.py`) validando 503 con `STUDIO_ENABLED=false` y 200 con `STUDIO_ENABLED=true`.
  - `R8-10`: Targets `run-studio` / `test-studio` en `Makefile`, validación completa de docs, Compose (3 archivos), AST/tests Python y pipeline frontend completo.
