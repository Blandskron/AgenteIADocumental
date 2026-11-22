# 09 — Propuestas de Evolución Arquitectónica

- **Principio rector:** No proponer reemplazos completos de arquitectura, ni motores de persistencia redundantes, ni microservicios injustificados. Respetar la topología existente (PostgreSQL 16 + `pgvector`, roles SQL de privilegio mínimo, perfiles opcionales en Docker Compose, aislamiento local-first).
- **Evaluación obligatoria:** Cada propuesta responde de forma explícita a las **16 preguntas arquitectónicas** de la Etapa X.

---

## Propuesta ARQ-01 — Estabilización transaccional y de contratos en `KnowledgeStudioServices` y `AgentOrchestratorServices`

1. **¿Por qué es necesaria?** Ambos servicios opcionales fallan contra PostgreSQL real y en integración mutua debido a mismatches de esquema y configuración.
2. **¿Qué evidencia demuestra la necesidad?** `StudioRepositoryPg` escribe columnas inexistentes en `studio.artifacts`; `AuditLogger` usa columnas inexistentes en `public.audit_logs`; `PostgresRunsRepository` descarta `pending_approval`/`code_executions`; `agents.yml:41` apunta a `auth-service:8000`; `approval_node.py:98` envía `template_id="executive_brief"`; ambos fugan conexiones con `create_engine()` por request.
3. **¿Qué usuario se beneficia?** Todos los usuarios que activen `--profile studio` o `--profile agents`.
4. **¿Qué componente la implementa?** `KnowledgeStudioServices`, `AgentOrchestratorServices`, `scripts/database/agents/provision_role.sql`, `docker/compose/agents.yml`, `frontend/docker-entrypoint.d/20-runtime-config.sh`.
5. **¿Qué contratos existentes reutiliza?** Esquemas `011_notifications_audit.sql`, `013_knowledge_studio.sql`, `014_agent_orchestrator.sql`, `ArtifactContent`, `DocumentExportServices /api/v1/exports/chat-message/pdf`.
6. **¿Qué cambios introduce?** Alinear SQL con tablas reales (`studio.artifact_versions`, `public.audit_logs`), singleton `Engine` en `lifespan`, otorgar `SELECT` en `audit_logs` a `agent_runtime`, añadir columnas JSONB opcionales o join con `agent_approvals`, corregir URLs de Auth/Export/Studio y alinear `ADR_AGENT_ORCHESTRATOR.md` con la máquina de estados real en Python.
7. **¿Afecta la base de datos?** Mínimamente: 1 migración aditiva opcional para `agents.agent_runs` (`code_executions`, `studio_handoff`) + `GRANT SELECT` acotado a `agent_runtime`.
8. **¿Afecta la seguridad?** Positivamente: restaura auditoría real, cierra endpoints sin JWT en Studio, valida identidad en vivo en `agents.yml` y sanitiza `state["goal"]`.
9. **¿Afecta los permisos?** Solo añade `SELECT` sobre sus propios registros/tenant en `public.audit_logs` para `agent_runtime` y JWT obligatorio en utilidades de Studio.
10. **¿Afecta el frontend?** Solo inyectar `VITE_KNOWLEDGE_STUDIO_BASE_URL` y `VITE_AGENT_ORCHESTRATOR_BASE_URL` en `20-runtime-config.sh`.
11. **¿Afecta el modo local?** Lo repara; 100 % local.
12. **¿Aumenta consumo de recursos?** Lo reduce (elimina fugas de pools SQLAlchemy).
13. **¿Necesita un servicio nuevo?** No.
14. **¿Puede ejecutarse como extensión opcional?** Ya vive en `--profile studio` y `--profile agents`.
15. **¿Cómo se probaría?** Nueva suite pytest contra PostgreSQL 16 real en `ci-integration.yml` + prueba de integración Agent → Studio → Export.
16. **¿Cómo se revertiría?** Reversión estándar de commits y migración aditiva sin afectar tablas core `public.*`.

---

## Propuesta ARQ-02 — Cola asíncrona basada en PostgreSQL (`SKIP LOCKED`) para Ingesta/OCR y Knowledge Studio

1. **¿Por qué es necesaria?** Ingerir PDFs escaneados con OCR español o generar artefactos Studio con Ollama local supera fácilmente timeouts HTTP síncronos.
2. **¿Qué evidencia demuestra la necesidad?** `RagDocumentEmbeddingServices` procesa síncronamente en `/upload`; `KnowledgeStudioServices/app/interfaces/worker.py` no corre en ningún proceso y `POST /studio/jobs` deja filas en `PENDING` indefinidamente.
3. **¿Qué usuario se beneficia?** Usuarios individuales, investigadores y pymes con PDFs pesados, escaneos o CPU local.
4. **¿Qué componente la implementa?** `RagDocumentEmbeddingServices` y `KnowledgeStudioServices`.
5. **¿Qué contratos existentes reutiliza?** Patrón `FOR UPDATE SKIP LOCKED` ya probado en `DocumentAccessServices` (`document_deletions`), `GET /documents/{id}/status` y tabla `studio.studio_jobs`.
6. **¿Qué cambios introduce?** Tarea `asyncio`/worker ligero dentro del `lifespan` (con `BoundedSemaphore` configurable) que reclama filas `PENDING`, ejecuta OCR/embeddings o generación LLM (usando `TenantLLMConfigResolver`) y actualiza estado y `studio.artifact_versions`.
7. **¿Afecta la base de datos?** No requiere tablas nuevas (reutiliza `documents.status` y `studio.studio_jobs`; solo índice parcial opcional sobre `status = 'PENDING'`).
8. **¿Afecta la seguridad?** Mantiene aislamiento por `tenant_id` y re-verifica permisos antes de guardar artefactos (`ACCESS_REVOKED`).
9. **¿Afecta los permisos?** No.
10. **¿Afecta el frontend?** Polling/SSE de progreso en `DocumentSearchPage` y `StudioPage` (endpoints `/status` y `/jobs/{id}` ya existen).
11. **¿Afecta el modo local?** Mejora estabilidad en CPU sin añadir Redis ni RabbitMQ.
12. **¿Aumenta consumo de recursos?** Controlado por `MAX_CONCURRENT_JOBS=1` por defecto (evita picos OOM).
13. **¿Necesita un servicio nuevo?** No.
14. **¿Puede ejecutarse como extensión opcional?** Configurable por variable de entorno (`ASYNC_INGEST_ENABLED`).
15. **¿Cómo se probaría?** Tests de concurrencia `SKIP LOCKED`, recuperación ante reinicio y timeout OCR.
16. **¿Cómo se revertiría?** Flag de entorno para volver a modo síncrono inmediato.

---

## Propuesta ARQ-03 — Enriquecimiento del pipeline RAG: OCR español, tablas MIT, citas exactas y SSE real

1. **¿Por qué es necesaria?** Resuelve las mayores causas de frustración real: fallo en PDFs escaneados, falta de `spa.traineddata`, tablas rotas, citas sin número de página, pseudo-streaming SSE y fuga de `</document_context>`.
2. **¿Qué evidencia demuestra la necesidad?** Auditoría de `RagDocumentEmbeddingServices/Dockerfile`, `pdf_extractor.py`, `docx_extractor.py`, `ChatSourceResponse` y `chat_routes.py`.
3. **¿Qué usuario se beneficia?** Todos los perfiles (individuales, estudiantes, pymes, empresas).
4. **¿Qué componente la implementa?** `RagDocumentEmbeddingServices`, `RagDocumentChatServices`, `frontend/`.
5. **¿Qué contratos existentes reutiliza?** `chunk_metadata` (ya contiene `page` y `section`), `ChatSourceResponse` (extensión retrocompatible con campos opcionales), protocolo SSE existente.
6. **¿Qué cambios introduce?** `tesseract-ocr-spa` + `pypdfium2` + `pdfplumber` + `openpyxl` + `python-pptx`; exponer `page`, `section`, `chunk_index`, `rrf_score` en `ChatSourceResponse`; streaming real del SDK OpenAI; escape `</document_context>`; gate de evidencia mínima.
7. **¿Afecta la base de datos?** No (usa `chunk_metadata` JSONB existente).
8. **¿Afecta la seguridad?** Mejora: neutraliza cierre de etiquetas XML en chunks y valida zip-bomb en XLSX/PPTX.
9. **¿Afecta los permisos?** No.
10. **¿Afecta el frontend?** `SourceList` muestra página/sección y abre `DocumentPreviewModal` en la página; `SafeMarkdown` añade soporte de tablas.
11. **¿Afecta el modo local?** 100 % local y open source (MIT / Apache-2.0).
12. **¿Aumenta consumo de recursos?** Moderado en ingesta (+200–500 MB pico solo al ejecutar OCR en PDF escaneado); nulo en chat.
13. **¿Necesita un servicio nuevo?** No.
14. **¿Puede ejecutarse como extensión opcional?** OCR PDF y reranker posterior (ARQ-05) configurables por flags.
15. **¿Cómo se probaría?** `run_rag_format_matrix.py` real + nueva evaluación `run_eval_baseline` contra PostgreSQL + E5 real + tests Playwright.
16. **¿Cómo se revertiría?** Reversión modular por extractor; campos nuevos en `ChatSourceResponse` son opcionales y retrocompatibles.

---

## Propuesta ARQ-04 — Versionado documental, etiquetas y hallazgos estructurados persistentes

1. **¿Por qué es necesaria?** Permite trazabilidad histórica (`v1` vs `v2`), clasificación transversal por etiquetas y persistencia de vencimientos/obligaciones con flujo de revisión humana.
2. **¿Qué evidencia demuestra la necesidad?** Ausencia de `document_versions`, `tags` y `document_findings` en `scripts/database/schemas/`; analizadores actuales efímeros sobre snippets de 300 chars.
3. **¿Qué usuario se beneficia?** Investigadores, profesionales, pymes y empresas.
4. **¿Qué componente la implementa?** `scripts/database/`, `DocumentLibraryServices`, `RagDocumentEmbeddingServices`, `AgentOrchestratorServices`, `frontend/`.
5. **¿Qué contratos existentes reutiliza?** `documents`, `document_assignments`, `notifications`, `audit_logs`, `agents.agent_approvals`.
6. **¿Qué cambios introduce?** Migración aditiva con `public.document_versions`, `public.tags`, `public.document_tags` y `agents.document_findings`; endpoints CRUD en `DocumentLibraryServices` y revisión humana en `AgentOrchestratorServices`/`DocumentAccessServices`.
7. **¿Afecta la base de datos?** Sí — migración aditiva idempotente en `scripts/database/migrations/` con roles actualizados.
8. **¿Afecta la seguridad?** Mantiene aislamiento por `tenant_id` y `ON DELETE CASCADE` desde `public.documents` para evitar fugas tras borrado.
9. **¿Afecta los permisos?** Hereda permisos del documento padre; gestionar etiquetas corporativas puede restringirse a `TENANT_ADMIN`/`LEADER`.
10. **¿Afecta el frontend?** Chips de etiquetas, selector de versión en detalle y bandeja de hallazgos pendientes de revisión.
11. **¿Afecta el modo local?** 100 % local.
12. **¿Aumenta consumo de recursos?** Disco proporcional a versiones retenidas (configurable por `MAX_VERSIONS_PER_DOCUMENT`).
13. **¿Necesita un servicio nuevo?** No.
14. **¿Puede ejecutarse como extensión opcional?** Hallazgos proactivos siguen ligados al perfil opcional `agents` (o capa determinista ligera).
15. **¿Cómo se probaría?** Tests SQL de integridad/roles + pruebas de comparación `v1` vs `v2` + flujo HITL.
16. **¿Cómo se revertiría?** Migración aditiva reversible sin alterar columnas existentes de `public.documents`.

---

## Propuesta ARQ-05 — Reranker ONNX opcional y consolidación de memoria E5 (Optimización local-first)

1. **¿Por qué es necesaria?** Elevar Precision@5 en corpora grandes (≥8–16 GB RAM) y reducir ~600 MB de RAM duplicada al cargar `multilingual-e5-small` en dos contenedores separados (`chat` e `embedding`).
2. **¿Qué evidencia demuestra la necesidad?** `RagDocumentChatServices` y `RagDocumentEmbeddingServices` cargan cada uno ~600 MB de `torch` + E5; `search_similar` carece de cross-encoder.
3. **¿Qué usuario se beneficia?** Usuarios en 8 GB RAM (ahorro de memoria) y 16–32 GB RAM (mayor precisión RAG).
4. **¿Qué componente la implementa?** `RagDocumentChatServices` (reranker opcional) y `RagDocumentEmbeddingServices` (endpoint interno opcional `/internal/embed` o modo compartido).
5. **¿Qué contratos existentes reutiliza?** `EmbeddingProvider` interface en `RagDocumentChatServices`.
6. **¿Qué cambios introduce?** Flag `RERANKER_ENABLED=false` con `BAAI/bge-reranker-v2-m3` ONNX INT8; evaluación opcional de cliente HTTP interno hacia el modelo E5 de ingesta para evitar doble carga en RAM en perfiles de 8 GB.
7. **¿Afecta la base de datos?** No.
8. **¿Afecta la seguridad?** Comunicación estrictamente en red interna Docker sin exposición de puertos.
9. **¿Afecta los permisos?** No.
10. **¿Afecta el frontend?** No (opcionalmente indicador de estado en `/settings/ai`).
11. **¿Afecta el modo local?** Lo optimiza directamente.
12. **¿Aumenta consumo de recursos?** Reranker añade ~650 MB solo si se activa; compartir E5 ahorra ~600 MB.
13. **¿Necesita un servicio nuevo?** No.
14. **¿Puede ejecutarse como extensión opcional?** Sí (`RERANKER_ENABLED=false` por defecto).
15. **¿Cómo se probaría?** Comparativa A/B de NDCG@5, MRR, latencia P95 y RSS RAM en `scripts/eval/`.
16. **¿Cómo se revertiría?** Mantener `RERANKER_ENABLED=false` y proveedor E5 local por defecto.
