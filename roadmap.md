# Roadmap de Evolución — Blandskron Documental (Etapa 2)

> Documento vivo de ejecución para llevar **Blandskron Documental** al siguiente nivel: plataforma documental inteligente, configurable desde la web, con recuperación híbrida de alta precisión y generación de artefactos verificables con evidencia.

**Última actualización:** 2026-11-21  
**Estado actual:** **Fases 0, 1, 2, 3 y 4 completadas + `R5-05` terminada (25 / 29 tareas terminadas)** — Pendientes únicamente 4 mejoras opcionales/hardening de **Fase 5**.

---

## Convención de estados

- `pendiente` — Planificada y lista para priorizar o iniciar.
- `en progreso` — En desarrollo o verificación activa.
- `terminada` — Implementada, probada y validada según `AGENTS.md`.

---

## Resumen de avance

| Fase | Enfoque | Total | Pendiente | En progreso | Terminada |
| --- | --- | ---: | ---: | ---: | ---: |
| **Fase 0** | Higiene técnica, historial único y base de evaluación | 4 | 0 | 0 | 4 |
| **Fase 1** | Configuración de IA (Groq) desde la web y degradación honesta | 5 | 0 | 0 | 5 |
| **Fase 2** | Motor RAG híbrido, búsqueda moderna y UX de chat | 5 | 0 | 0 | 5 |
| **Fase 3** | Ingesta idempotente y fuentes Markdown/ZIP (Opción O1) | 4 | 0 | 0 | 4 |
| **Fase 4** | Knowledge Studio P0 (artefactos con citas verificadas) | 6 | 0 | 0 | 6 |
| **Fase 5** | Hardening de seguridad y extensiones P1+ bajo demanda | 5 | 4 | 0 | 1 |
| **Total** | | **29** | **4** | **0** | **25** |

---

## 1. Fases completadas (resumen depurado)

- **Fase 0 (`R0-01`–`R0-04`) — `terminada`:** Limpieza de planes, `Makefile` para 11 servicios, historial único `conversation_messages` y corpus sintético `S1`–`S5` (`scripts/eval/run_eval_baseline.py`).
- **Fase 1 (`R1-01`–`R1-05`) — `terminada`:** Migración `tenant_integrations` + roles mínimos, `SecretsCipher` (`secrets1.`), permiso `manage_ai_settings`, APIs DRF `/api/integrations/groq/*`, `GroqConfigResolver` dinámico con `provider_status` tipificado y vista web `/settings/ai`.
- **Fase 2 (`R2-01`–`R2-05`) — `terminada`:** Chunking estructural con `metadata.page`/`section`, índices `HNSW` + `content_tsv` GIN + trigram, recuperación híbrida `vector + FTS + RRF`, blindaje anti prompt-injection `<document_context>`, `SafeMarkdown` anti-XSS con citas `[Fuente N]` clicables y SSE opcional (`?stream=true`).
- **Fase 3 (`R3-01`–`R3-04`) — `terminada`:** Idempotencia por `Idempotency-Key` + `content_sha256`, extractor `MarkdownNormalizer` (frontmatter/wikilinks/tags/`.obsidian/`), endpoint seguro por lote `POST /api/v1/documents/import-batch` (anti zip-bomb/symlink/path-traversal) y tarjeta UI `Importar Markdown / ZIP` en `ApplicationsPage`.
- **Fase 4 (`R4-01`–`R4-06`) — `terminada`:** Esquema SQL aislado `studio.*` con trigger automático `FRESH -> STALE`, motor `KnowledgeStudioServices` (revalidación en vuelo `ACCESS_REVOKED`, caché por huella, 4 familias P0, validador de groundedness ≥ 95 % con reparación acotada y CSV anti formula-injection), registro de renderers `source_type="studio_artifact"` en `DocumentExportServices`, vista web `/studio` y gate automatizado `scripts/eval/run_studio_eval_gate.py`.

---

## 2. Plan activo pendiente — Fase 5 (Hardening y extensiones P1+)

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R5-01` | `pendiente` | P1 | `AuthServices`, `frontend/`, `docker/` | **Migración de sesión web a cookies `HttpOnly` + protección CSRF.** Retirar tokens de acceso/refresco del almacenamiento del navegador (deuda documentada en `frontend/AUDIT.md`), coordinando CORS, cookies `SameSite` y renovación silenciosa entre Auth, Nginx y Frontend. **Done:** login/refresh/logout y suite de verificación de instalación aprobados sin tokens en storage JS. |
| `R5-02` | `pendiente` | P1 | `AuthServices`, `scripts/database/`, `frontend/` | **Activar `audit_logs` persistente y visor administrativo de auditoría.** Aprovechar la tabla `audit_logs` (`011_notifications_audit.sql`) para registrar acciones administrativas críticas (cambios de IA, permisos, borrados documentales, exportaciones y eventos Studio) con consulta filtrable para `TENANT_ADMIN`/superadmin, siempre sin payloads sensibles. **Done:** registro persistente + paginación + test de no-exposición de secretos. |
| `R5-03` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Visualizaciones deterministas en Studio (P1).** Mapas conceptuales interactivos alimentados por `[[wikilinks]]`/evidencia (`reactflow`), diagramas Mermaid con `securityLevel: 'strict'` y gráficos numéricos generados **exclusivamente** desde celdas verificadas de una `evidence_table`. **Done:** render sanitizado en cliente, cero valores inventados y export SVG/PNG. |
| `R5-04` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Quizzes y flashcards locales con verificación de citas (P1).** Generación validada (única respuesta correcta + explicación citada; descarte automático de preguntas inválidas) y práctica local offline con repaso espaciado simple (SM-2 sin telemetría). **Done:** 100 % de preguntas válidas tras validador y práctica offline funcional sin Groq. |
| `R5-05` | `terminada` | P2 | `docs/`, `backend/` | **ADR de extensibilidad: proveedores OpenAI-compatible/Ollama y MCP de solo lectura.** Documentado en [docs/ADR_EXTENSIBILITY_LLM_MCP.md](docs/ADR_EXTENSIBILITY_LLM_MCP.md) con allowlist SSRF, perfil opcional Compose y modelo de amenazas MCP. |
