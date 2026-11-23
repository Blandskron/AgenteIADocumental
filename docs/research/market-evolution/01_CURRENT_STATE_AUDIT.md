# 01 — Auditoría Integral del Estado Actual

- **Repositorio:** `https://github.com/Blandskron/AgenteIADocumental`
- **Rama auditada:** `develop`
- **Commit SHA auditado:** `5a4fac256199f5418fcd5d1de749bdf422d2e407` (`5a4fac2`)
- **Fecha de auditoría:** 22 de noviembre de 2026
- **Estado del árbol de trabajo al inicio:** Limpio (`git status --short` vacío), 0 issues abiertas y 0 PRs abiertos en `origin`.
- **Alcance:** Auditoría directa sobre código fuente (`backend/`, `frontend/`, `scripts/`, `docker/`, `compose.yaml`, `docs/`, `.github/`, `tests/`, `brain/`, `index.html`, `README.md`, `AGENTS.md`), complementada con ejecución de comprobaciones locales no destructivas.

---

## 1. Metodología y clasificación de estados

Cada capacidad y componente se clasifica estrictamente en uno de los seis estados definidos:

- **IMPLEMENTADO Y VERIFICADO:** Existe implementación en código y pruebas ejecutadas satisfactoriamente en esta auditoría o en CI documentado con evidencia verificable.
- **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL:** Existe código, pero no pudo comprobarse su ejecución real end-to-end contra sus dependencias reales (por ejemplo, PostgreSQL o runtime externo).
- **IMPLEMENTADO PARCIALMENTE:** Existen piezas funcionales incompletas, desconectadas entre capas o con errores comprobados en integración real.
- **DOCUMENTADO:** Aparece en documentación o ADRs sin implementación real en código.
- **NO ENCONTRADO:** No se identificó implementación dentro del alcance auditado.
- **NO APLICA:** La funcionalidad no corresponde a la filosofía o alcance del producto.

---

## 2. Comprobaciones locales no destructivas ejecutadas en esta auditoría

Ejecutadas el `2026-11-22` sobre `develop@5a4fac2` sin modificar código ni instalar dependencias:

| Comprobación | Comando | Resultado real | Observaciones |
|---|---|---|---|
| Enlaces Markdown | `python scripts/ci/check_docs_links.py` | **PASS** | Todos los enlaces relativos en raíz y `docs/` resuelven. |
| Contratos de agentes y sandbox | `python scripts/ci/check_agents_contract.py` | **PASS** | Verifica defaults `false`, `read_only`, `cap_drop`, `internal: true`. |
| Gate sintético de Studio | `python scripts/eval/run_studio_eval_gate.py` | **PASS** | `passed=True` usando generador JSON mockeado (sin LLM ni PostgreSQL). |
| Tests `AgentOrchestratorServices` | `python -m pytest tests -q` (en servicio) | **36 passed, 2 skipped** (0.51s) | Todos en memoria/mock; 0 tests contra PostgreSQL real. |
| Tests `KnowledgeStudioServices` | `python -m pytest tests -q` (en servicio) | **11 passed, 1 skipped** (0.18s) | Todos en memoria/mock; 0 tests contra PostgreSQL real. |
| Tests `CodeSandboxRunner` | `python -m pytest tests -q` (en servicio) | **3 passed, 1 skipped** (0.11s) | `test_live_deno_deny_all_blocks_fs_env_and_network` omitido (Deno no instalado en host). |
| Frontend Unit Tests | `npm test` (en `frontend/`) | **138 passed, 0 failed** (4.2s) | 31 archivos de prueba con `node --test`. |
| Frontend Lint & Typecheck | `npm run lint` y `npm run typecheck` | **PASS** | `eslint src --max-warnings=0` y `tsc --noEmit` sin errores. |

> **Nota de honestidad técnica:** Las suites que requieren contenedores PostgreSQL/Docker en ejecución (`AuthServices` Django, servicios FastAPI core contra PostgreSQL, `verify.mjs` E2E y Playwright browser specs) no se levantaron en esta fase de solo lectura; su existencia y cobertura se verificaron directamente en los archivos de test y en `.github/workflows/ci-fast.yml` y `ci-integration.yml`.

---

## 3. Revalidación de la arquitectura conocida

| Capacidad documentada | Estado auditado | Evidencia real en código |
|---|---|---|
| React 19 + TypeScript + Vite | **IMPLEMENTADO Y VERIFICADO** | `frontend/package.json` (`react@19.3.1`, `typescript@6.0.3`, `vite@8.3.7`), 138 tests + lint + typecheck OK. |
| Django para identidad | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** (local) / CI activo | `backend/AuthServices` (Django 6.0.10, DRF 3.18.3, SimpleJWT 5.5.1, JWT RS256, `secrets1.` Fernet). |
| Servicios Python y APIs (14 servicios) | **IMPLEMENTADO PARCIALMENTE** (core operativo; opcionales con brechas) | 12 servicios FastAPI + 1 Django + 1 Deno en `backend/`. Ver inventario completo en Sección 4. |
| PostgreSQL 16 + `pgvector` | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** (local) / CI activo | `docker/postgres/Dockerfile` (`postgres:16.16-alpine3.24` + `pgvector v0.8.7`), 33 tablas en `public`, `studio`, `agents`. |
| Recuperación híbrida HNSW + FTS + RRF | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `scripts/database/migrations/008_hnsw_and_fts_indexes.sql` y `VectorRepositoryPgVector.search_similar` (`RRF_K = 60`). |
| Embeddings locales multilingües en CPU | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `intfloat/multilingual-e5-small` (384 dims, `device="cpu"`, `local_files_only=True`) empaquetado en `docker/models/e5/Dockerfile`. |
| Ollama como proveedor local | **IMPLEMENTADO PARCIALMENTE** | Enrutamiento en `AuthServices` (`ollama_integrations.py`), `RagDocumentChatServices` y `AgentOrchestratorServices`; `ollama.yml` ignora `OLLAMA_HOST_PORT` y `_PULL_STATES` vive en memoria. |
| Groq como proveedor externo opcional | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `GroqConfigResolver` + `GroqLLMProvider` + cifrado `SecretsCipher`. |
| Control de acceso multiempresa y permisos granulares | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `003_tenants.sql`, 13+ roles SQL de privilegio mínimo, filtros por `tenant_id`, `owner_groups`, `document_assignments`. |
| Ingesta documental con OCR | **IMPLEMENTADO PARCIALMENTE** | OCR funciona en imágenes PNG/JPEG/TIFF vía `pytesseract`, pero **solo instala `eng.traineddata` (sin español)** y `PdfExtractor` (`pypdf`) **no hace fallback OCR en PDFs escaneados**. |
| Importación Markdown/ZIP | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `POST /api/v1/documents/import-batch` (`ImportMarkdownBatch`, protección zip-bomb, máx. 100 archivos / 20 MiB). |
| Integración opcional con Google Drive | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `GoogleDriveImportServices` (`GOOGLE_DRIVE_ENABLED=false`, OAuth PKCE S256, scope `drive.file`, importación manual por lotes). |
| Knowledge Studio opcional | **IMPLEMENTADO PARCIALMENTE** | Servicio HTTP existe, pero **sin LLM**, **sin worker en ejecución**, **mismatch crítico de columnas SQL en `studio.artifacts`**, y UI desconectada en `StudioPage.tsx`. |
| Servidor MCP de solo lectura | **IMPLEMENTADO PARCIALMENTE** | `POST /api/v1/mcp` JSON-RPC 2.0 con 4 herramientas `readOnlyHint: true` y JWT RS256; las 2 herramientas de artefactos fallarán en PostgreSQL real por el mismatch de `studio.artifacts`. |
| Orquestación de agentes opcional | **IMPLEMENTADO PARCIALMENTE** | `AgentOrchestratorServices` operativo en pruebas mock (36/36), pero con `AUTH_IDENTITY_URL` erróneo en `agents.yml` (`:8000` en vez de `:8001`), mismatch en `AuditLogger` y `PostgresRunsRepository`, y handoff a Studio roto. |
| LangGraph con persistencia de checkpoints | **DOCUMENTADO** (reemplazado por implementación propia) | `ADR_AGENT_ORCHESTRATOR.md` declara `langgraph` + `langgraph-checkpoint-postgres`, pero `requirements.txt` **no los incluye**; `ResearchAgentGraph` es una máquina de estados propia en Python puro con checkpoints JSONB. |
| Análisis documental de fechas, montos y cláusulas | **IMPLEMENTADO PARCIALMENTE** | Extractores regex deterministas en `AgentOrchestratorServices` (`/analyze`), pero operan solo sobre snippets truncados a 300 chars de `run["sources"]`, no sobre el documento completo. |
| Flujos de aprobación humana (HITL) | **IMPLEMENTADO PARCIALMENTE** | Lógica de pausa `WAITING_APPROVAL` y `POST /resume` con `FOR UPDATE` existe, pero `PostgresRunsRepository` descarta `pending_approval` al persistir en `agents.agent_runs`. |
| Code Mode en sandbox local | **IMPLEMENTADO Y VERIFICADO** (estático) / **PARCIAL** (runtime) | `CodeSandboxRunner` con Deno `--deny-all`, `--no-remote`, `clearEnv: true`, red `internal: true`; 3 presets curados; sin límite de concurrencia interno ni auth en `/execute`. |
| Exportación de resultados | **IMPLEMENTADO SIN VERIFICACIÓN FUNCIONAL** | `DocumentExportServices` (PDF ReportLab en subproceso aislado, 30 días retención) + MD/CSV en Agentes + CSV en Studio. |
| Auditoría | **IMPLEMENTADO PARCIALMENTE** | `public.audit_logs` y `GET /api/audit-logs/` operativos en Auth/Access/MCP; **rotos en `AgentOrchestratorServices`** por nombres de columna incorrectos y falta de `SELECT` en `agent_runtime`. |
| Docker Compose, Landing GitHub Pages y Demo | **IMPLEMENTADO Y VERIFICADO** | `compose.yaml` + 14 overlays en `docker/compose/`, `index.html` (1088 líneas), 24 capturas WebP claro/oscuro, video narrado 04:00 min. |

---

## 4. Inventario técnico completo de los 14 servicios backend

### 4.1 `backend/AuthServices` (Puerto 8001)
- **Propósito:** Identidad central, sesiones JWT RS256 y cookies HttpOnly, RBAC multiempresa, configuración de IA (Groq/Ollama) con cifrado `secrets1.` y consulta de `audit_logs`.
- **Arquitectura y dependencias:** Django 6.0.10, DRF 3.18.3, SimpleJWT 5.5.1, `cryptography` (Fernet), Gunicorn.
- **Endpoints clave:** `/api/users/{setup-status,register,login,token/refresh,logout,me,change-password,password-reset/request,google/login}/`, `/api/users/session/{login,refresh,logout}/`, CRUD de usuarios/tenants/áreas/membresías/grupos, `/api/integrations/{ai/provider,groq/*,ollama/*}`, `/api/audit-logs/`.
- **Seguridad:** Claves RSA-2048 autogeneradas (`core/jwt_keys.py`), throttling en BD (`LoginAttemptBudget`), `SecretsCipher` con rotación de hasta 4 claves, allowlist de modelos y hosts en Ollama.
- **Cobertura de pruebas:** 9 archivos de test (`users/tests.py`, `test_ai_integrations.py`, `test_ollama_integrations.py`, `test_registration_and_oidc.py`, `test_hardening_audit_session.py`, `test_secrets_cipher.py`, etc.).
- **Limitaciones comprobadas:**
  1. `users/registration.py:35-42` (`_issue_tokens_for_user`) usa `RefreshToken.for_user(user)` en vez de `MyTokenObtainPairSerializer.get_token(user)`, omitiendo claims multiempresa en el primer token tras `/register/` o `/google/login/`.
  2. Sin rotación de refresh token (`ROTATE_REFRESH_TOKENS` ausente).
  3. `CookieSessionLoginView` omite throttling (`login_retry_after`) y auditoría (`audit_auth_event`).
  4. `_PULL_STATES` (`ollama_integrations.py:78`) vive en memoria del worker Gunicorn.
  5. `password-reset/request/` es un stub sin generación de token ni envío SMTP real.

### 4.2 `backend/RagDocumentEmbeddingServices` (Puerto 8003)
- **Propósito:** Recepción, validación, almacenamiento local, extracción de texto/OCR, chunking estructural y generación de embeddings locales `intfloat/multilingual-e5-small` (384d, CPU).
- **Dependencias:** FastAPI 0.162, SQLAlchemy 2.0.40, `psycopg[binary]`, `sentence-transformers==5.6.0`, `torch==2.15.0` CPU, `pypdf==6.21.4`, `python-docx==1.1.2`, `pillow==13.0.0`, `pytesseract==0.3.13`, Tesseract 5.5.4.
- **Endpoints:** `POST /api/v1/documents/upload`, `POST /api/v1/documents/import-batch`, `POST /api/v1/documents/{id}/{process,reindex}`, `GET /api/v1/documents/{id}/status`.
- **Cobertura de pruebas:** 8 archivos (`test_structural_chunking.py`, `test_native_ocr.py`, `test_markdown_batch_import.py`, `test_idempotency_and_markdown.py`, etc.).
- **Limitaciones comprobadas:**
  1. Imagen Docker de Tesseract solo incluye `eng.traineddata` (sin `spa.traineddata`).
  2. `PdfExtractor` no detecta PDFs escaneados ni invoca OCR (falla con `ExtractionError`).
  3. Sin soporte para XLSX, PPTX, HTML ni extracción estructurada de tablas en PDF/CSV; tablas DOCX se apilan al final perdiendo posición.
  4. Procesamiento síncrono en el request HTTP (sin cola asíncrona real); sin versionado documental; deduplicación SHA-256 solo aplica si llega header `Idempotency-Key`.

### 4.3 `backend/RagDocumentChatServices` (Puerto 8002)
- **Propósito:** Recuperación híbrida HNSW + FTS (`spanish`) + RRF (`k=60`) con permisos multiempresa y generación de respuestas citadas mediante Ollama, Groq o proveedor `openai_compatible`.
- **Endpoints:** `POST /api/v1/chat/ask?stream={bool}`, `GET /api/v1/health*`.
- **Cobertura de pruebas:** 8 archivos (`test_hybrid_and_injection.py`, `test_groq_resolver.py`, `test_ollama_provider_routing.py`, `test_openai_compatible_ssrf.py`, etc.).
- **Limitaciones comprobadas:**
  1. `page` y `section` se extraen en ingesta pero **no se inyectan al LLM ni se exponen en `ChatSourceResponse`**.
  2. Sin reranking, sin reescritura de consultas multi-turno y sin gate programático de evidencia insuficiente (`min_similarity_score=0.0`).
  3. SSE (`stream=True`) es pseudo-streaming (espera respuesta completa y luego trocea cada 160 chars).
  4. No neutraliza etiquetas `</document_context>` incrustadas dentro de chunks recuperados.
  5. `GroqConfigResolver.resolve_active_provider` solo enruta `ollama` o `groq` desde BD (omite `openai_compatible`); mensaje de error genérico menciona solo Groq; no adapta el presupuesto de contexto (`24 * 1200` chars) para modelos locales de ventana pequeña.

### 4.4 `backend/DocumentSearchServices` (Puerto 8004)
- **Propósito:** Búsqueda FTS + trigram, detalle de documento, paginación de chunks y selección para chat (`POST /chat-selection`).
- **Cobertura de pruebas:** 2 archivos (`test_current_identity.py`, `test_document_access.py`) — cobertura baja.
- **Limitaciones comprobadas:** Filtro `source` consulta `metadata_->>'source' == source`, incompatible con `metadata["source"]["kind"]` guardado en `UploadDocument`; comodines `%`/`_` sin escapar en `ilike`; sin ordenación por relevancia `ts_rank_cd`.

### 4.5 `backend/DocumentAccessServices` (Puerto 8005)
- **Propósito:** Preview inline, descarga autenticada, lectura de contenido, borrado en cascada con recuperación asíncrona (`document_deletions`), asignaciones de documentos y notificaciones.
- **Cobertura de pruebas:** 8 archivos (concurrencia, permisos, borrado, path resolver, contratos).
- **Limitaciones comprobadas:** `/preview` rechaza `.docx`, `.md` y `.csv` con HTTP 415 (solo PDF/TXT/imágenes).

### 4.6 `backend/DocumentLibraryServices` (Puerto 8006)
- **Propósito:** Carpetas jerárquicas privadas, favoritos, recientes y marcadores batch, con bloqueos `FOR KEY SHARE` y advisory locks compartidos con Drive.
- **Cobertura de pruebas:** 9 archivos (concurrencia, integridad, permisos, rol runtime).
- **Limitaciones comprobadas:** Sin etiquetas/tags, sin carpetas compartidas por tenant/área, sin edición de metadatos documentales ni gestión de retención; llamada síncrona a `AuthServices /api/users/me/` en cada request.

### 4.7 `backend/DocumentTransferServices` (Puerto 8007)
- **Propósito:** Bitácora privada de cargas/descargas con máquina de estados monótona (`transfer_state.py`).
- **Cobertura de pruebas:** 10 archivos.
- **Limitaciones comprobadas:** Registro declarativo enviado desde el cliente; sin purga automática por retención.

### 4.8 `backend/ConversationServices` (Puerto 8008)
- **Propósito:** Persistencia privada de conversaciones, mensajes y documentos vinculados al chat.
- **Cobertura de pruebas:** 2 archivos (`test_conversations.py`, `test_current_identity.py`) — cobertura baja.
- **Limitaciones comprobadas:** Sin `body_limit` dedicado; sin conversaciones compartidas ni retención automática.

### 4.9 `backend/ProfileServices` (Puerto 8015)
- **Propósito:** Perfil de contacto privado y avatar normalizado con Pillow (JPEG ≤1 MiB en `BYTEA`), concurrencia optimista (`expected_version`) y verificación de identidad vía función SQL `SECURITY DEFINER` (sin dependencia HTTP a Auth).
- **Cobertura de pruebas:** 9 archivos.
- **Estado:** Muy sólido y bien endurecido (`read_only`, `cap_drop`, límites de memoria/CPU).

### 4.10 `backend/DocumentExportServices` (Puerto 8016)
- **Propósito:** Exportación privada de instantáneas de chat en PDF mediante ReportLab 4.2.5 en subproceso aislado (`15 s` timeout, ≤1 MiB, ≤20 páginas, retención 30 días, `ETag` + `pdf_sha256`).
- **Cobertura de pruebas:** 14 archivos.
- **Limitaciones comprobadas:** Solo expone `POST /exports/chat-message/pdf` (el registro `studio_artifact` en `renderer_registry.py` no tiene ruta HTTP); renderiza texto plano sin formato Markdown enriquecido; sin purga automática programada de filas expiradas.

### 4.11 `backend/GoogleDriveImportServices` (Puerto 8017)
- **Propósito:** Conector opcional OAuth 2.0 + PKCE S256 (scope mínimo `drive.file`, cifrado `drive1.` con rotación de claves) para importación manual por lotes (≤25 archivos) hacia Ingesta.
- **Cobertura de pruebas:** 8 archivos.
- **Limitaciones comprobadas:** Siempre se levanta en Compose core aunque `GOOGLE_DRIVE_ENABLED=false`; solo importación manual (sin sincronización incremental, sin detección de cambios/eliminaciones ni herencia de permisos externos).

### 4.12 `backend/KnowledgeStudioServices` (Puerto 8018, perfil `--profile studio`)
- **Propósito:** Plantillas de artefactos documentales, validación de groundedness, exportación CSV segura, mapas conceptuales, gráficos verificados, SM-2 y servidor MCP de solo lectura (`POST /api/v1/mcp`).
- **Cobertura de pruebas:** 7 archivos (11 passed, 1 skipped), **0 tests contra PostgreSQL real**.
- **Brechas críticas comprobadas:**
  1. `StudioRepositoryPg` hace `INSERT`/`SELECT` de columnas `content`, `version`, `groundedness_score` en `studio.artifacts` que **no existen** en `013_knowledge_studio.sql`, e ignora por completo `studio.artifact_versions`.
  2. Sin cliente LLM ni contenedor worker activo (`POST /studio/jobs` encola filas `PENDING` indefinidamente).
  3. `_get_studio_repo()` crea un nuevo `create_engine()` en cada request sin cerrarlo (fuga de conexiones).
  4. `StudioQuotaGuard` vive en memoria y no está conectado a `app/main.py`.
  5. Endpoints utilitarios (`/validate`, `/export-csv`, `/mermaid/validate`, `/graph`, `/chart-series`, `/flashcards/review`, `/templates`) carecen de JWT auth.
  6. `validate_groundedness` retorna `score=1.0, valid=True` cuando `claims=[]`.

### 4.13 `backend/AgentOrchestratorServices` (Puerto 8019, perfil `--profile agents`)
- **Propósito:** Orquestación multi-paso con checkpoints, cliente MCP, herramientas de búsqueda/acceso, plantillas especializadas, analizadores deterministas, HITL, cuotas, auditoría y Code Mode.
- **Cobertura de pruebas:** 27 archivos (36 passed, 2 skipped), **0 tests contra PostgreSQL real ni servicios HTTP reales**.
- **Brechas críticas comprobadas:**
  1. `docker/compose/agents.yml:41` apunta `AUTH_IDENTITY_URL` al puerto `8000` en lugar de `8001`.
  2. No usa `langgraph` ni `langgraph-checkpoint-postgres` pese a `ADR_AGENT_ORCHESTRATOR.md`.
  3. `AuditLogger` usa columnas inexistentes (`id`, `target_type`, `target_id`) en `public.audit_logs` y `agent_runtime` carece de `SELECT`.
  4. `PostgresRunsRepository` descarta `pending_approval`, `code_executions` y `studio_handoff` al actualizar `agents.agent_runs`.
  5. Handoff a Knowledge Studio roto (`template_id="executive_brief"` y esquema `content` incompatibles).
  6. Fuga de pool SQLAlchemy en `_get_runtime_components()`; ejecución síncrona con SSE falso; `state["goal"]` sin sanitizar; `detect_prompt_injection_patterns()` sin usar; `system_prompt` sin instrucciones de fallback JSON para modelos Ollama pequeños.

### 4.14 `backend/CodeSandboxRunner` (Puerto interno 8090, perfil `--profile code-mode`)
- **Propósito:** Ejecución aislada de transformaciones TypeScript/JavaScript puras sobre evidencia sanitizada mediante subproceso Deno `--deny-all --no-remote --no-npm --v8-flags=--max-old-space-size=128` con `clearEnv: true` y red Docker `internal: true`.
- **Cobertura de pruebas:** 1 archivo (3 passed, 1 skipped porque `deno` no está en el host).
- **Limitaciones comprobadas:** Sin auth entre contenedores en `POST /execute`; sin límite de concurrencia interno en `server.ts`; gVisor (`runsc`) comentado por defecto; regex estática evadible por ofuscación (aunque mitigada por `--deny-all`).

---

## 5. Auditoría de Base de Datos, Frontend, Despliegue, CI/CD e Higiene

### 5.1 Base de datos (`scripts/database/`)
- **Fortalezas:** 33 tablas bien estructuradas en 3 esquemas (`public`, `studio`, `agents`), extensiones `pgcrypto`/`pg_trgm`/`vector`, índices HNSW + GIN FTS + trigram, 13+ roles de privilegios mínimos con scripts `verify_role*.sql`, funciones `SECURITY DEFINER` con `search_path` fijo, y trigger cross-schema `studio.mark_artifacts_stale_on_document_change()`.
- **Brechas:** Sin versionado documental (`document_versions`), sin tablas de etiquetas (`tags`/`document_tags`), sin tablas de entidades/obligaciones/vencimientos estructurados, sin políticas de retención/purga automática ni RLS nativo, y sin script automatizado de backup (solo `restore_postgres16.sh`).

### 5.2 Frontend (`frontend/`)
- **Fortalezas:** Solo 3 dependencias runtime (`react`, `react-dom`, `lucide-react`), bundle principal ligero (`220.8 KB` JS + `43.8 KB` CSS) con lazy loading por vista, Design System *Floating Glass* con fuente `Inter` local y temas claro/oscuro, 15 rutas, 138 unit tests y 6 suites Playwright con `@axe-core/playwright`.
- **Brechas:** `20-runtime-config.sh` no inyecta `VITE_KNOWLEDGE_STUDIO_BASE_URL` ni `VITE_AGENT_ORCHESTRATOR_BASE_URL`; `StudioPage.tsx` desconectada de `KnowledgeStudioServices` y con datos hardcodeados en flashcards/quizzes; `DocumentPreviewModal` usa `<iframe sandbox="" />` sin PDF.js ni salto a página/fragmento; `SafeMarkdown.tsx` no renderiza tablas Markdown; `LoginPage.tsx` no renderiza botón funcional de Google OIDC; sin Command Palette (`Ctrl+K`), sin drag-and-drop multiarchivo, sin onboarding post-registro y sin uso de hooks React 19.

### 5.3 Despliegue, CI/CD e higiene del repositorio
- **Fortalezas:** Arranque core en 1 comando con secretos autogenerados (`init_secrets.sh`), puertos en `127.0.0.1`, CI rápido e integración muy maduros (Trivy en 13 imágenes, `pip-audit`, concurrencia SQL, pruebas de actualización PostgreSQL 16).
- **Hallazgo crítico de seguridad/higiene (`brain/`):** El archivo `brain/ead4e5a8-11b7-4f5d-83cd-cf5d56766830/scratch/check_google_oauth.py` está rastreado en Git (`brain/` falta en `.gitignore`) y contiene una credencial hardcodeada (`postgresql://postgres:admin1234@localhost:5432/documents_db`).
- **Desigualdad de hardening:** 11 servicios core y `knowledge-studio-service` carecen de `mem_limit`/`cpus`/`pids_limit` en Compose; `init_secrets.sh` escribe secretos con `chmod 0444`; `ollama/ollama:latest` no está fijada por digest.

---

## 6. Referencias cruzadas

- Capacidades del ecosistema: [02_FUNCTIONAL_CAPABILITIES_RESEARCH.md](./02_FUNCTIONAL_CAPABILITIES_RESEARCH.md)
- Matriz de brechas y fortalezas: [03_FEATURE_GAP_MATRIX.md](./03_FEATURE_GAP_MATRIX.md)
- Auditoría detallada de Agentes, Studio, MCP y Sandbox: [07_AGENT_AND_MCP_AUDIT.md](./07_AGENT_AND_MCP_AUDIT.md)
- Auditoría de Frontend: [08_FRONTEND_PRODUCT_EXPERIENCE.md](./08_FRONTEND_PRODUCT_EXPERIENCE.md)
- Autonomía Local-First: [10_LOCAL_FIRST_COMPLIANCE.md](./10_LOCAL_FIRST_COMPLIANCE.md)
