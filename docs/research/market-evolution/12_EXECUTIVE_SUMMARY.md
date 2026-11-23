# 12 — Resumen Ejecutivo y Estrategia de Producto

- **Repositorio:** `https://github.com/Blandskron/AgenteIADocumental` (`develop@5a4fac2`, 22 de noviembre de 2026)
- **Naturaleza de esta entrega:** Auditoría técnica exhaustiva, investigación de capacidades y roadmap de evolución basado en evidencia de código (**cero modificaciones de código en esta fase**).

---

## 1. Diagnóstico general: qué es hoy Blandskron Documental

Blandskron Documental ya cuenta con una **base de ingeniería excepcionalmente madura en su núcleo**:

- **Núcleo operativo y bien endurecido:** 11 servicios core (Auth Django RS256 multiempresa, Embeddings locales `multilingual-e5-small` 384d en CPU, Chat RAG híbrido HNSW+FTS+RRF, Búsqueda, Acceso con asignaciones y borrado recuperable, Biblioteca con integridad transaccional, Transferencias, Conversaciones, Perfil con avatares normalizados, Exportación PDF aislada con ReportLab y conector Google Drive opcional con PKCE S256), más frontend React 19 + TypeScript de solo 3 dependencias runtime (`138/138` tests unitarios, `eslint` y `tsc` limpios) con Design System *Floating Glass* claro/oscuro y fuente local `Inter`.
- **Autonomía local-first genuina:** Cero dependencias cloud obligatorias en runtime, cero telemetría externa, secretos autogenerados localmente, puertos restringidos a `127.0.0.1` y CI/CD con auditoría Trivy de 13 imágenes y pruebas de concurrencia SQL.

Sin embargo, la auditoría directa sobre el código reveló **brechas críticas ocultas por el uso exclusivo de mocks en las capas más recientes**:

1. **Fallos garantizados contra PostgreSQL real en servicios opcionales:**
   - `KnowledgeStudioServices` (`StudioRepositoryPg`) consulta e inserta columnas inexistentes (`content`, `version`, `groundedness_score`) en `studio.artifacts`, ignora `studio.artifact_versions`, no tiene cliente LLM ni worker activo y fuga pools `create_engine()` por request.
   - `AgentOrchestratorServices` (`AuditLogger`) usa nombres de columna inexistentes en `public.audit_logs` y carece de `SELECT`; `PostgresRunsRepository` descarta `pending_approval`/`code_executions`/`studio_handoff`; el handoff a Studio envía un `template_id` y JSON incompatibles; `docker/compose/agents.yml:41` apunta a `auth-service:8000` en vez de `:8001`; y `ADR_AGENT_ORCHESTRATOR.md` declara `langgraph` aunque la implementación real es una máquina de estados propia en Python puro.
2. **Brechas de calidad RAG y usabilidad en español:**
   - Tesseract en Docker solo incluye `eng.traineddata` (sin `spa.traineddata`) y `PdfExtractor` falla en PDFs escaneados sin fallback OCR.
   - `page` y `section` se extraen en ingesta pero se pierden antes del prompt LLM y de la API `ChatSourceResponse`; el visor PDF no salta a página ni resalta fragmentos; `SafeMarkdown` no renderiza tablas; SSE es pseudo-streaming; y `run_eval_baseline.py` es un proxy léxico que no mide el RAG real.
3. **Higiene y seguridad puntual:**
   - `brain/ead4e5a8-11b7-4f5d-83cd-cf5d56766830/scratch/check_google_oauth.py` está rastreado en Git con una credencial local (`admin1234`); `RagDocumentChatServices` no escapa `</document_context>`; `AuthServices` omite claims en el primer token tras `/register/`; y `20-runtime-config.sh` no inyecta las URLs de Studio ni Agents.

---

## 2. Estrategia de producto (Etapa XI) — Una sola plataforma abierta

**Filosofía única e innegociable:** Toda capacidad desarrollada forma parte del software gratuito y open source (MIT). Las funciones avanzadas pueden requerir perfiles opcionales o más RAM/GPU local, **nunca una licencia comercial obligatoria ni suscripciones**.

| Segmento | Necesidad principal | Propuesta de valor de Blandskron Documental | Perfil recomendado |
|---|---|---|---|
| **Usuarios individuales** | Organizar y consultar documentos privados gratis sin subirlos a la nube | Instalación en 1 comando, búsqueda híbrida instantánea, OCR en español y chat local con citas verificables | Core + `--profile local-llm` (`qwen2.5:3b` en 8 GB RAM) |
| **Investigadores y estudiantes** | Procesar fuentes, construir conocimiento estructurado, grafos y estudiar sin límites | Colecciones, informes verificados con citas exactas, matrices de evidencia, tarjetas SM-2 y cuestionarios reales en Knowledge Studio | Core + `--profile local-llm` + `--profile studio` (16 GB RAM) |
| **Profesionales y pymes** | Analizar contratos, controlar vencimientos, montos, obligaciones y comparar versiones | Versionado documental, extracción estructurada con procedencia, alertas revisables por humanos y exportación PDF/CSV | Core + `--profile local-llm` + `--profile agents` (16 GB RAM) |
| **Empresas** | Gobernanza, aislamiento multiempresa, auditoría, RBAC y control total de infraestructura | Roles SQL de privilegio mínimo, RBAC por empresa/área/grupo, auditoría exportable, sandbox Deno aislado y MCP local de solo lectura | Stack completo + perfiles opcionales y políticas de backup |

---

## 3. Dirección estratégica y prioridades inmediatas

El orden correcto de ejecución evita construir sobre deuda oculta:

1. **Ola 1 — P0 (Estabilizar y asegurar lo ya construido, `EVO-001` a `EVO-006`):** Limpiar `brain/`, reparar `agents.yml` y `20-runtime-config.sh`, alinear SQL de `KnowledgeStudioServices` y `AgentOrchestratorServices` con pruebas contra PostgreSQL 16 real, cerrar brechas de `AuthServices`/anti-prompt-injection y habilitar OCR español + fallback en PDFs escaneados.
2. **Ola 2 — P1 (Multiplicar valor real sin cambiar la arquitectura, `EVO-007` a `EVO-013`):** Citas con página/sección y navegación en visor, tablas MIT + XLSX/PPTX, cola PostgreSQL `SKIP LOCKED` + Studio con LLM y UI real, SSE real + herramienta MCP híbrida + compatibilidad Ollama 3B–8B, evaluación RAG real, mejoras UX React 19 y CLI de backup/perfiles.
3. **Ola 3 — P2 (Diferenciación sostenible, `EVO-014` a `EVO-018`):** Versionado documental, etiquetas, inteligencia documental proactiva persistida con revisión humana, reranker ONNX opcional + optimización RAM E5, y conector de carpeta local sincronizada.
4. **Ola 4 — P3 (Experimental bajo demanda, `EVO-019`):** Layout pesado (`Docling`) y voz offline (`faster-whisper`/`Piper`) únicamente tras validar métricas y demanda.

---

## 4. Qué hace única y competitiva a la plataforma

Blandskron Documental ocupa un espacio propio difícil de igualar: combina **privacidad local-first genuina** (PostgreSQL 16 + `pgvector` + embeddings CPU + Ollama + Deno sandbox sin red) con **rigor de ingeniería empresarial** (roles SQL de privilegio mínimo, RBAC multiempresa, cifrado `secrets1.` con rotación, trazabilidad de citas y separación estricta entre detección y acción humana) bajo **licencia MIT sin muros de pago ni dependencia de proveedores**. Completar las brechas P0 y P1 convertirá esa arquitectura en una plataforma de referencia plenamente confiable.
