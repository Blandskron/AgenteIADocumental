# Roadmap de Evolución — Blandskron Documental (Etapa 2) — COMPLETADO

> **Estado: 37 / 37 tareas terminadas (100 %).** Todas las fases planificadas (Fases 0–5 + Fase 6 de expansión operativa y extensibilidad) están implementadas y verificadas.

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
| **Total** | | **37** | **0** | **0** | **37** |

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
