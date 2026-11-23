# 11 — Roadmap de Evolución Basado en Evidencia

- **Commit base:** `develop@5a4fac2` (22 de noviembre de 2026).
- **Principio rector:** Fortalecer lo que existe, reparar primero los fallos comprobados en código/SQL/integración, completar capacidades parcialmente implementadas y evolucionar únicamente donde exista valor verificable en operación **100 % gratuita, open source y local-first**.
- **Niveles de prioridad:**
  - **P0 — Crítico:** Seguridad, higiene, fallos SQL/runtime comprobados, pérdida de datos y funcionamiento local.
  - **P1 — Alto valor:** Confiabilidad, calidad RAG/OCR, completitud de Studio/Agentes y experiencia de uso.
  - **P2 — Avanzado:** Versionado documental, etiquetas, inteligencia documental proactiva persistida, reranker opcional y conectores incrementales.
  - **P3 — Experimental:** Layout pesado (`Docling`), voz local (Whisper/Piper) y webhooks salientes.

---

## P0 — Crítico (Estabilización, seguridad y contratos rotos)

### `EVO-001` — Limpieza de artefacto temporal con credencial y endurecimiento de higiene Git
- **Problema real:** Existe un script temporal rastreado en Git con una credencial de base de datos hardcodeada (`admin1234`).
- **Evidencia técnica:** `brain/ead4e5a8-11b7-4f5d-83cd-cf5d56766830/scratch/check_google_oauth.py` (línea 4) y ausencia de `brain/` en `.gitignore`.
- **Resultado esperado:** Cero archivos temporales ni credenciales rastreadas en el repositorio.
- **Componente responsable:** Raíz del repositorio (`.gitignore`, historial de limpieza en rama).
- **Dependencias:** Ninguna.
- **Complejidad:** Baja · **Impacto:** Crítico.
- **Riesgos:** Ninguno en runtime.
- **Consumo estimado:** Nulo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** `git ls-files brain` vacío; `brain/` incluido en `.gitignore`; regla en CI que bloquee rutas temporales.
- **Pruebas obligatorias:** Verificación `git ls-files`, `check_docs_links.py` y `ci-fast`.
- **Condiciones de reversión:** No aplica (higiene obligatoria).

### `EVO-002` — Corrección de conectividad runtime en perfiles opcionales y frontend Docker
- **Problema real:** Al levantar los perfiles `agents`, `studio` o `local-llm`, los servicios no resuelven correctamente Auth, URLs de frontend ni el puerto parametrizado de Ollama.
- **Evidencia técnica:** `docker/compose/agents.yml:41` (`auth-service:8000` en vez de `:8001`), `frontend/docker-entrypoint.d/20-runtime-config.sh` (omite `VITE_KNOWLEDGE_STUDIO_BASE_URL` y `VITE_AGENT_ORCHESTRATOR_BASE_URL`), `docker/compose/ollama.yml:11` (ignora `OLLAMA_HOST_PORT`).
- **Resultado esperado:** Configuración runtime coherente en todos los perfiles de Docker Compose.
- **Componente responsable:** `docker/compose/`, `frontend/`.
- **Dependencias:** Ninguna.
- **Complejidad:** Baja · **Impacto:** Crítico.
- **Riesgos:** Cambios en variables deben sincronizarse con aserciones de `.github/workflows/ci-fast.yml`.
- **Consumo estimado:** Nulo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** `agent-orchestrator-service` valida `/api/users/me/` contra `:8001`; `window.__BLANDSKRON_CONFIG__` expone ambas URLs; `ollama.yml` respeta `OLLAMA_HOST_PORT`.
- **Pruebas obligatorias:** `docker compose config --quiet` en todos los overlays + aserciones de `ci-fast.yml` + smoke HTTP en contenedor.
- **Condiciones de reversión:** Reversión directa de los 3 archivos de configuración.

### `EVO-003` — Reparación de persistencia PostgreSQL, pool de conexiones y seguridad HTTP en `KnowledgeStudioServices`
- **Problema real:** `StudioRepositoryPg` falla contra PostgreSQL real por consultar/insertar columnas inexistentes en `studio.artifacts`, ignora `studio.artifact_versions`, fuga pools de SQLAlchemy por request y expone 7 endpoints utilitarios sin JWT.
- **Evidencia técnica:** `backend/KnowledgeStudioServices/app/infrastructure/studio_repository_pg.py:216-280`, `app/main.py:62-70`, `scripts/database/schemas/013_knowledge_studio.sql`, `validate_groundedness` retornando `score=1.0` con `claims=[]`.
- **Resultado esperado:** CRUD real de artefactos versionados sobre `studio.artifacts` + `studio.artifact_versions`, pool singleton en `lifespan`, JWT obligatorio en endpoints protegidos y verificación en vivo en `POST /api/v1/mcp`.
- **Componente responsable:** `KnowledgeStudioServices`.
- **Dependencias:** `EVO-002`.
- **Complejidad:** Media · **Impacto:** Crítico.
- **Riesgos:** Cambios en contratos internos de Studio requieren actualizar `test_studio_api.py`.
- **Consumo estimado:** Reduce RAM/conexiones DB · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Crear, listar, versionar y leer artefactos vía REST y MCP contra PostgreSQL 16 real sin errores SQL; `claims=[]` devuelve `valid=False` si la plantilla exige afirmaciones.
- **Pruebas obligatorias:** Nueva suite pytest contra PostgreSQL 16 real (incluyendo trigger `STALE` y MCP `list_studio_artifacts`/`get_studio_artifact`).
- **Condiciones de reversión:** Revertir cambios del repositorio Python; esquema `013_knowledge_studio.sql` no cambia.

### `EVO-004` — Reparación de persistencia PostgreSQL, auditoría, handoff a Studio y exportación PDF en `AgentOrchestratorServices`
- **Problema real:** `AuditLogger` usa nombres de columna inexistentes en `public.audit_logs` y carece de `SELECT`; `PostgresRunsRepository` descarta `pending_approval`/`code_executions`/`studio_handoff`; el handoff a Studio usa `template_id` y JSON incompatibles; `pdf_export_client` llama a una ruta inexistente (`/chat-snapshot`); hay fuga de `create_engine()` y `state["goal"]` omite sanitización.
- **Evidencia técnica:** `audit_logger.py:65-98`, `runs_repository.py:235-269`, `approval_node.py:98`, `pdf_export_client.py`, `research_graph.py:187,213`, `agents/provision_role.sql:39`.
- **Resultado esperado:** Runs, aprobaciones HITL, auditoría, exportación PDF y handoff a Studio operando de extremo a extremo contra PostgreSQL 16 y servicios reales, con `ADR_AGENT_ORCHESTRATOR.md` alineado a la máquina de estados real.
- **Componente responsable:** `AgentOrchestratorServices`, `scripts/database/agents/`, `docs/ADR_AGENT_ORCHESTRATOR.md`.
- **Dependencias:** `EVO-002`, `EVO-003`.
- **Complejidad:** Media · **Impacto:** Crítico.
- **Riesgos:** Requiere sincronizar `agents/verify_role.sql` y migración aditiva para columnas de `agents.agent_runs`.
- **Consumo estimado:** Reduce conexiones DB · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Ejecución real de agente → pausa `WAITING_APPROVAL` → `POST /resume` → guardado real en `studio.artifact_versions` + registro visible en `public.audit_logs` + exportación PDF HTTP 200.
- **Pruebas obligatorias:** Suite pytest contra PostgreSQL 16 real + prueba de integración Agent → Studio → Export + `verify_agents_all.py`.
- **Condiciones de reversión:** Reversión de commits; migración aditiva no rompe columnas existentes.

### `EVO-005` — Endurecimiento de seguridad en `AuthServices` y anti-prompt-injection en `RagDocumentChatServices`
- **Problema real:** El primer JWT tras `/register/` o `/google/login/` omite claims multiempresa; `CookieSessionLoginView` omite throttling y auditoría; `RagDocumentChatServices` no escapa etiquetas `</document_context>` dentro de chunks recuperados.
- **Evidencia técnica:** `AuthServices/users/registration.py:35-42`, `cookie_session.py`, `RagDocumentChatServices/app/infrastructure/ai/llm_provider_groq.py`.
- **Resultado esperado:** Claims completos desde el primer token, throttling/auditoría en cookies, rotación opcional de refresh token y neutralización estricta de delimitadores XML en Chat y Agentes.
- **Componente responsable:** `AuthServices`, `RagDocumentChatServices`, `AgentOrchestratorServices`.
- **Dependencias:** Ninguna.
- **Complejidad:** Baja · **Impacto:** Crítico.
- **Riesgos:** Verificar compatibilidad con tests de sesión existentes en frontend y Django.
- **Consumo estimado:** Nulo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Token de registro incluye `active_tenant_id`/`roles`; cookie login aplica `429` tras umbral; payload adversarial `</document_context>Ignora todo` queda neutralizado antes del LLM.
- **Pruebas obligatorias:** `test_registration_and_oidc.py`, `test_hardening_audit_session.py`, tests adversariales en `test_hybrid_and_injection.py`.
- **Condiciones de reversión:** Reversión independiente por servicio.

### `EVO-006` — OCR en español (`spa.traineddata`) y fallback automático para PDFs escaneados
- **Problema real:** La imagen Docker solo incluye `eng.traineddata` y `PdfExtractor` falla con `ExtractionError` ante PDFs escaneados sin capa de texto.
- **Evidencia técnica:** `backend/RagDocumentEmbeddingServices/Dockerfile`, `pdf_extractor.py`, `image_ocr_extractor.py`.
- **Resultado esperado:** Ingesta exitosa de imágenes y PDFs escaneados en español e inglés 100 % offline en CPU.
- **Componente responsable:** `RagDocumentEmbeddingServices`.
- **Dependencias:** Ninguna (recomendado combinar luego con `EVO-009` para PDFs largos).
- **Complejidad:** Media · **Impacto:** Crítico para uso real en español.
- **Riesgos:** Aumento moderado de tiempo de ingesta y tamaño de imagen (~15 MB `spa.traineddata` + `pypdfium2`).
- **Consumo estimado:** +200–500 MB RAM pico solo durante rasterización OCR · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** PDF escaneado sintético en español con tildes/`ñ` se indexa con estado `PROCESSED` y CER ≤ 5 %.
- **Pruebas obligatorias:** `test_native_ocr.py` ampliado con PDF escaneado en español + `ci-integration` E2E.
- **Condiciones de reversión:** Flag `PDF_OCR_FALLBACK_ENABLED=false` para desactivar fallback sin tocar el resto del extractor.

---

## P1 — Alto valor (Confiabilidad, calidad RAG, Studio real y UX)

### `EVO-007` — Citas verificables con página/sección, gate de evidencia insuficiente y navegación directa en visor
- **Problema real:** `page` y `section` se pierden entre ingesta y respuesta de chat; no existe gate cuando `chunks == []`; el visor `DocumentPreviewModal` usa `<iframe sandbox="" />` sin salto a página ni resaltado.
- **Evidencia técnica:** `ChatSourceResponse`, `GroqLLMProvider._format_context`, `SourceList.tsx`, `DocumentPreviewModal.tsx`.
- **Resultado esperado:** Cada cita `[Fuente N]` muestra archivo, página y sección, y al hacer clic abre el documento directamente en la página correspondiente con el fragmento resaltado; si no hay evidencia suficiente, el chat informa honestamente sin alucinar.
- **Componente responsable:** `RagDocumentChatServices`, `frontend/`.
- **Dependencias:** `EVO-005`.
- **Complejidad:** Media · **Impacto:** Alto.
- **Riesgos:** Si se incorpora `pdfjs-dist` (Apache-2.0), debe cargarse en chunk lazy para no inflar el bundle inicial.
- **Consumo estimado:** Bajo (+1–2 MB chunk lazy) · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** `ChatSourceResponse` devuelve `page`, `section`, `chunk_index`, `rrf_score`; respuesta directa ante 0 chunks; clic en `[Fuente N]` abre página exacta en navegador.
- **Pruebas obligatorias:** Tests de contrato Chat + unitarios frontend + Playwright E2E con verificación axe-core.
- **Condiciones de reversión:** Campos nuevos en API son opcionales; fallback a texto crudo en `SourceList`.

### `EVO-008` — Parsing estructural de tablas (PDF/DOCX/CSV) y soporte ofimático MIT (XLSX/PPTX)
- **Problema real:** Tablas PDF se aplanan, tablas DOCX pierden su posición, CSV se lee como texto crudo y no se soportan XLSX ni PPTX.
- **Evidencia técnica:** `pdf_extractor.py`, `docx_extractor.py`, `plain_text_extractor.py`, `SUPPORTED_MIME_TYPES`.
- **Resultado esperado:** Conservación de tablas en Markdown dentro de chunks coherentes y soporte seguro (anti-zip-bomb) de XLSX y PPTX usando librerías MIT (`pdfplumber`, `openpyxl`, `python-pptx`).
- **Componente responsable:** `RagDocumentEmbeddingServices`, `DocumentSearchServices` (corregir también bug de filtro `source`).
- **Dependencias:** `EVO-006`.
- **Complejidad:** Media · **Impacto:** Alto.
- **Riesgos:** Archivos XLSX enormes requieren tope de filas/celdas para evitar OOM.
- **Consumo estimado:** <150 MB RAM extra en ingesta · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Matriz `run_rag_format_matrix.py` ejecutada con archivos reales PDF/DOCX/XLSX/PPTX/CSV con exactitud de tablas ≥ 90 %.
- **Pruebas obligatorias:** Suite de extractores + pruebas zip-bomb + `run_rag_format_matrix.py`.
- **Condiciones de reversión:** Desactivar MIME types nuevos en `SUPPORTED_MIME_TYPES`.

### `EVO-009` — Cola asíncrona PostgreSQL (`SKIP LOCKED`) para Ingesta/OCR y Worker LLM real en Knowledge Studio
- **Problema real:** Ingesta pesada/OCR bloquea requests HTTP; `KnowledgeStudioServices` carece de cliente LLM y de worker activo para procesar `studio.studio_jobs`.
- **Evidencia técnica:** `upload_document.py`, `process_document_worker.py`, `KnowledgeStudioServices/app/interfaces/worker.py`, `studio_runner.py`.
- **Resultado esperado:** Procesamiento asíncrono confiable sin añadir Redis/RabbitMQ, generación real de artefactos en Studio usando Ollama o Groq (`TenantLLMConfigResolver`), cuotas conectadas y UI `StudioPage.tsx` conectada a jobs, artefactos reales, `VerifiedVisualsPanel` y flashcards/quizzes generados desde documentos.
- **Componente responsable:** `RagDocumentEmbeddingServices`, `KnowledgeStudioServices`, `frontend/`.
- **Dependencias:** `EVO-003`, `EVO-006`.
- **Complejidad:** Alta · **Impacto:** Alto.
- **Riesgos:** Concurrencia en CPU local si se lanzan múltiples jobs Ollama en paralelo (mitigar con `MAX_CONCURRENT_JOBS=1`).
- **Consumo estimado:** Controlado por semáforo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Subir PDF escaneado devuelve `202` y pasa a `PROCESSED`; crear job en `StudioPage` genera artefacto versionado con citas verificadas reales y visualizaciones deterministas.
- **Pruebas obligatorias:** Tests de concurrencia `SKIP LOCKED`, revocación mid-flight `ACCESS_REVOKED` y E2E Studio en Playwright.
- **Condiciones de reversión:** Flag `ASYNC_INGEST_ENABLED=false` para modo síncrono.

### `EVO-010` — Streaming SSE real, herramienta RAG semántica vía MCP y compatibilidad con modelos Ollama 3B–8B
- **Problema real:** El streaming SSE de Chat y Agentes es simulado; el agente no tiene herramienta de recuperación semántica (solo FTS/ILIKE); el `system_prompt` del agente no instruye el formato JSON de fallback para modelos Ollama pequeños; `GroqConfigResolver` omite `openai_compatible`.
- **Evidencia técnica:** `chat_routes.py`, `runs_routes.py`, `research_graph.py:287-292`, `groq_config_resolver.py`, `mcp_readonly.py`.
- **Resultado esperado:** Tokens transmitidos en tiempo real desde Ollama/Groq, herramienta MCP `search_documents_hybrid` (solo lectura), presupuesto de contexto adaptado a la ventana del modelo y guía explícita de JSON fallback en el agente + catálogo Ollama actualizado con requisitos de RAM en `SettingsAIPage`.
- **Componente responsable:** `RagDocumentChatServices`, `KnowledgeStudioServices` (MCP), `AgentOrchestratorServices`, `AuthServices`, `frontend/`.
- **Dependencias:** `EVO-003`, `EVO-004`.
- **Complejidad:** Media · **Impacto:** Alto.
- **Riesgos:** Cancelación de streams SSE en Nginx requiere `X-Accel-Buffering: no`.
- **Consumo estimado:** Reduce latencia percibida (TTFT) · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Primer delta SSE llega antes de finalizar la generación; agente con `qwen2.5:3b` ejecuta tool-calling o JSON fallback con éxito; `search_documents_hybrid` respeta aislamiento por tenant.
- **Pruebas obligatorias:** Tests de streaming incremental, tests MCP híbrido y prueba con Ollama local.
- **Condiciones de reversión:** Flag para modo no-streaming.

### `EVO-011` — Evaluación RAG reproducible sobre PostgreSQL + `multilingual-e5-small` reales
- **Problema real:** `scripts/eval/run_eval_baseline.py` solo ejecuta un proxy léxico en Python puro sin ejercitar embeddings, HNSW, FTS, RRF ni LLM.
- **Evidencia técnica:** `scripts/eval/run_eval_baseline.py`, `tests/fixtures/eval_corpus/`.
- **Resultado esperado:** Runner reproducible que mide `Recall@5/10`, `Precision@5`, `MRR`, `NDCG@5`, exactitud de citas, CER OCR y tasa de rechazo en preguntas sin respuesta (`S6`–`S8`).
- **Componente responsable:** `scripts/eval/`, `tests/fixtures/eval_corpus/`, `.github/workflows/ci-integration.yml`.
- **Dependencias:** `EVO-006`, `EVO-007`, `EVO-008`.
- **Complejidad:** Media · **Impacto:** Alto (gobierno de calidad).
- **Riesgos:** Tiempo de ejecución en CI (mitigar ejecutando en `ci-integration.yml`, no en `ci-fast.yml`).
- **Consumo estimado:** Solo durante evaluación · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Reporte JSON fechado en `.release-reports/RAG_REAL_EVAL.json` con métricas reales y umbrales verificados.
- **Pruebas obligatorias:** Ejecución limpia en `ci-integration.yml`.
- **Condiciones de reversión:** Mantener `run_eval_baseline.py` actual intacto como smoke rápido y añadir `run_eval_real.py`.

### `EVO-012` — Mejoras UX de alto impacto y modernización con React 19 (cero librerías extra)
- **Problema real:** `SafeMarkdown` no renderiza tablas; biblioteca/chat solo suben 1 archivo por clic; sin `Ctrl+K`; sin onboarding post-registro; `AuditLogsPage` fija a 50 filas sin paginación ni CSV; `LoginPage` sin botón OIDC ejecutable; 19 literales hex pendientes.
- **Evidencia técnica:** `SafeMarkdown.tsx`, `DocumentSearchPage.tsx`, `AuditLogsPage.tsx`, `LoginPage.tsx`, `primitives.css`, `chat.css`.
- **Resultado esperado:** Tablas Markdown seguras, drag-and-drop multiarchivo, Command Palette (`Ctrl+K`), checklist de primer inicio, auditoría paginada/exportable, botón OIDC funcional y adopción de `useActionState`/`useOptimistic`/`useDeferredValue`.
- **Componente responsable:** `frontend/`.
- **Dependencias:** `EVO-007`.
- **Complejidad:** Media · **Impacto:** Alto.
- **Riesgos:** Preservar 0 warnings ESLint, anti-XSS y cumplimiento WCAG AA claro/oscuro.
- **Consumo estimado:** Nulo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Todos los flujos verificados con unit tests + Playwright + `@axe-core/playwright` en claro y oscuro.
- **Pruebas obligatorias:** `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test`, `npm run build`, `npm run test:browser`.
- **Condiciones de reversión:** Incrementos pequeños por vista en PRs separados.

### `EVO-013` — Simplificación operativa: límites de recursos en Compose, digest Ollama, perfil Drive y CLI de backup
- **Problema real:** 11 servicios carecen de `mem_limit`/`cpus`/`pids_limit`; `ollama/ollama:latest` no tiene digest; `google-drive-import-service` arranca siempre en core; activar perfiles opcionales exige 4 flags `-f`; falta script único de backup.
- **Evidencia técnica:** `docker/compose/*.yml`, `docker/scripts/init_secrets.sh`, `scripts/database/tools/restore_postgres16.sh`.
- **Resultado esperado:** Todos los servicios con límites de recursos realistas, digest fijado en Ollama, script multiplataforma (`scripts/backup_postgres16.{sh,ps1}` + helper de arranque por perfil) y endurecimiento de permisos de secretos.
- **Componente responsable:** `docker/`, `scripts/`, `Makefile`, `README.md`.
- **Dependencias:** `EVO-002`.
- **Complejidad:** Baja · **Impacto:** Alto para adopción local.
- **Riesgos:** Ajustar `mem_limit` de `embedding`/`chat` con margen real (≥1.2 GB cada uno por `torch` + E5) para evitar OOM kills.
- **Consumo estimado:** Reduce riesgo de saturación de RAM · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** `docker compose config --quiet` válido; ciclo `backup → restore` probado offline en `bd-final-check`.
- **Pruebas obligatorias:** `ci-fast.yml` (`compose-contract`) + `verify_postgres_upgrade.mjs` + test backup/restore.
- **Condiciones de reversión:** Reversión directa en `docker/compose/` y `scripts/`.

---

## P2 — Avanzado (Capacidades diferenciales con base ya estabilizada)

### `EVO-014` — Versionado documental, etiquetas y carpetas compartidas por área/empresa
- **Problema real:** No es posible versionar documentos (`v1` → `v2`), etiquetarlos transversalmente ni compartir carpetas departamentales.
- **Evidencia técnica:** Ausencia de `document_versions`, `tags`, `document_tags` en `scripts/database/schemas/001_documents.sql` y `DocumentLibraryServices`.
- **Resultado esperado:** Historial de versiones con diff determinista, CRUD de etiquetas filtrables en Búsqueda/Chat y carpetas compartidas gobernadas por RBAC.
- **Componente responsable:** `scripts/database/`, `DocumentLibraryServices`, `RagDocumentEmbeddingServices`, `RagDocumentChatServices`, `frontend/`.
- **Dependencias:** `EVO-008`, `EVO-009`.
- **Complejidad:** Alta · **Impacto:** Alto.
- **Riesgos:** Controlar herencia de permisos y espacio en disco (`MAX_VERSIONS_PER_DOCUMENT`).
- **Consumo estimado:** Disco proporcional a versiones · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Migración idempotente + tests SQL de permisos/concurrencia + filtrado por tag en Chat y Biblioteca.
- **Pruebas obligatorias:** Suites SQL de integridad + pytest de servicios + Playwright.
- **Condiciones de reversión:** Migración aditiva sin alterar tablas existentes.

### `EVO-015` — Inteligencia documental proactiva persistida (hallazgos, vencimientos, obligaciones y revisión humana)
- **Problema real:** Los analizadores actuales operan sobre snippets de 300 chars, no persisten resultados ni permiten promover hallazgos aprobados a asignaciones/notificaciones.
- **Evidencia técnica:** `contract_comparator.py`, `expiration_detector.py`, `risk_assessor.py`, `014_agent_orchestrator.sql`.
- **Resultado esperado:** Extracción híbrida (determinista + Pydantic LLM) sobre documento completo con procedencia verificada por campo, bandeja de hallazgos en UI y promoción a `document_assignments`/`notifications` únicamente tras aprobación humana.
- **Componente responsable:** `AgentOrchestratorServices`, `DocumentAccessServices`, `scripts/database/`, `frontend/`.
- **Dependencias:** `EVO-004`, `EVO-009`, `EVO-014`.
- **Complejidad:** Alta · **Impacto:** Alto (diferenciador profesional/pyme).
- **Riesgos:** Falsos positivos en fechas o alto consumo de LLM si no se limita a análisis bajo demanda.
- **Consumo estimado:** Bajo en capa determinista; moderado en LLM bajo demanda · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Hallazgos con `provenance` verificable (`quote` en chunk), separación estricta `DETECTED → CONFIRMED → ACTIONED` auditada en `audit_logs`.
- **Pruebas obligatorias:** Tests de precisión por campo + tests HITL + Playwright.
- **Condiciones de reversión:** Perfil opcional `agents` desactivable sin afectar core.

### `EVO-016` — Reranker local ONNX opcional, reescritura de consultas y optimización de memoria E5
- **Problema real:** Corpora grandes con documentos similares requieren reranking para elevar Precision@5, y cargar `multilingual-e5-small` en dos contenedores consume ~1.2 GB RAM combinados.
- **Evidencia técnica:** `VectorRepositoryPgVector.search_similar`, `embedding_provider_local.py` duplicado en `chat` y `embedding`.
- **Resultado esperado:** `RERANKER_ENABLED=false` (ONNX INT8 `bge-reranker-v2-m3`) activable en equipos ≥8–16 GB RAM, reescritura opcional multi-turno y opción de cliente interno de embeddings para ahorrar ~600 MB RAM.
- **Componente responsable:** `RagDocumentChatServices`, `RagDocumentEmbeddingServices`.
- **Dependencias:** `EVO-011` (requiere línea base real para demostrar mejora).
- **Complejidad:** Media · **Impacto:** Medio-Alto.
- **Riesgos:** Latencia extra (+200–500 ms CPU) si se activa en equipos lentos.
- **Consumo estimado:** +650 MB si reranker activo / -600 MB si E5 compartido · **Compatibilidad offline:** Condicionada (reranker requiere ≥8–16 GB RAM).
- **Criterios de aceptación:** Mejora comprobada ≥ +0.05 en `NDCG@5` en `RAG_REAL_EVAL.json` sin degradar P95 por encima de 900 ms.
- **Pruebas obligatorias:** Benchmark A/B con `run_eval_real.py`.
- **Condiciones de reversión:** `RERANKER_ENABLED=false` por defecto.

### `EVO-017` — Conector de carpeta local sincronizada (SHA-256) y sincronización incremental opcional en Drive
- **Problema real:** No existe sincronización automática de una carpeta local del usuario ni detección de cambios en archivos ya importados desde Google Drive.
- **Evidencia técnica:** `ImportMarkdownBatch`, `GoogleDriveImportServices`.
- **Resultado esperado:** Sincronizador local en solo lectura (detecta altas/modificaciones/bajas por SHA-256 sin nube) y detección de delta por `modified_time`/`md5Checksum` bajo demanda en Drive.
- **Componente responsable:** `RagDocumentEmbeddingServices`, `GoogleDriveImportServices`.
- **Dependencias:** `EVO-009`, `EVO-014`.
- **Complejidad:** Media · **Impacto:** Medio-Alto.
- **Riesgos:** Gestión segura de borrados (marcar archivado o requerir confirmación antes de eliminar).
- **Consumo estimado:** Bajo · **Compatibilidad offline:** Total (carpeta local) / Opcional (Drive).
- **Criterios de aceptación:** Re-escanear carpeta sin cambios genera 0 reindexaciones; archivo modificado crea `v2` limpiamente.
- **Pruebas obligatorias:** Tests de alta/modificación/baja y protección path traversal/symlinks.
- **Condiciones de reversión:** Conector deshabilitado por defecto.

### `EVO-018` — Endurecimiento menor de `CodeSandboxRunner`, `ConversationServices` y sesiones Cookie HttpOnly
- **Problema real:** `CodeSandboxRunner` carece de token interno en `/execute` y límite de concurrencia interno; `ConversationServices` carece de `body_limit`; `AuthProvider` aún usa `localStorage` en lugar de cookies HttpOnly ya implementadas.
- **Evidencia técnica:** `CodeSandboxRunner/server.ts`, `ConversationServices`, `frontend/src/features/auth/`.
- **Resultado esperado:** Secreto interno + semáforo de concurrencia en sandbox + tests Deno en CI; `body_limit` en conversaciones; opción estable de sesión por cookie HttpOnly.
- **Componente responsable:** `CodeSandboxRunner`, `ConversationServices`, `AuthServices`, `frontend/`.
- **Dependencias:** `EVO-005`.
- **Complejidad:** Media · **Impacto:** Medio (seguridad en profundidad).
- **Riesgos:** Cookies HttpOnly exigen proxy same-origin en Nginx (configurar `proxy_pass` para `/api/`).
- **Consumo estimado:** Nulo · **Compatibilidad offline:** Total.
- **Criterios de aceptación:** Tests adversariales live de Deno (OOM, timeout, ofuscación) ejecutados en `ci-integration.yml`.
- **Pruebas obligatorias:** `test_sandbox_escape.py` live + tests de sesión frontend.
- **Condiciones de reversión:** Mantener modo Bearer como fallback configurable.

---

## P3 — Experimental (Validar demanda y coste antes de promover)

### `EVO-019` — Perfil opcional de layout avanzado (`Docling`) y capacidades locales de voz (`faster-whisper` / `Piper`)
- **Problema real:** PDFs científicos/escaneados con múltiples columnas y gráficos complejos superan a `pdfplumber`; usuarios con necesidades de accesibilidad o audio valoran transcripción/escucha offline.
- **Evidencia técnica:** Investigación Etapa VI (`Docling` MIT, `faster-whisper` MIT, `Piper` MIT).
- **Resultado esperado:** Perfiles estrictamente opcionales (`--profile advanced-ingest`, `--profile speech`) documentados para equipos ≥16–32 GB RAM.
- **Componente responsable:** Extensión opcional desacoplada (solo si benchmark P2 demuestra necesidad).
- **Dependencias:** `EVO-009`, `EVO-011`.
- **Complejidad:** Alta · **Impacto:** Selectivo.
- **Riesgos:** Consumo elevado de RAM (+1.5–4 GB) y peso de imagen Docker.
- **Consumo estimado:** Alto (≥16 GB RAM) · **Compatibilidad offline:** Condicionada a hardware.
- **Criterios de aceptación:** Prueba de concepto con benchmark real de RAM/latencia y 0 impacto en el stack core.
- **Pruebas obligatorias:** Benchmark aislado de memoria y precisión en `S6`/`S7`.
- **Condiciones de reversión:** No incluir en `compose.yaml` core; retirar perfil experimental si no supera el umbral coste/beneficio.
