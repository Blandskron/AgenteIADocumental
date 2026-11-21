# Roadmap de Evolución — Blandskron Documental (Etapa 2)

> Documento vivo de ejecución para llevar **Blandskron Documental** al siguiente nivel: plataforma documental inteligente, configurable desde la web, con recuperación híbrida de alta precisión y generación de artefactos verificables con evidencia.

**Última actualización:** 2026-11-21  
**Estado actual:** **Fase 0 y Fase 1 completadas (9 / 29 tareas terminadas)** — Siguiente bloque: **Fase 2 (Motor RAG híbrido, búsqueda moderna y UX de chat)**.

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
| **Fase 2** | Motor RAG híbrido, búsqueda moderna y UX de chat | 5 | 5 | 0 | 0 |
| **Fase 3** | Ingesta idempotente y fuentes Markdown/ZIP (Opción O1) | 4 | 4 | 0 | 0 |
| **Fase 4** | Knowledge Studio P0 (artefactos con citas verificadas) | 6 | 6 | 0 | 0 |
| **Fase 5** | Hardening de seguridad y extensiones P1+ bajo demanda | 5 | 5 | 0 | 0 |
| **Total** | | **29** | **20** | **0** | **9** |

---

## 1. Invariantes de arquitectura (reglas no negociables)

1. **Independencia de embeddings locales:** `intfloat/multilingual-e5-small` en CPU (`local_files_only=True`) jamás depende de Groq ni de conectividad externa; revocar o romper la clave LLM nunca puede afectar ingesta, búsqueda ni biblioteca.
2. **Autorización antes de recuperar:** todo filtro multi-tenant (propietario, asignaciones, área, grupos, `TENANT_ADMIN`) se ejecuta en el servidor antes de recuperar fragmentos o enviar contexto al LLM.
3. **Despliegue local simple:** `docker compose up` debe seguir funcionando sin añadir Redis, Celery, Elasticsearch ni GPU en el stack base.
4. **Cero secretos y datos reales:** toda prueba, benchmark o fixture usa documentos y credenciales 100 % sintéticas; ningún log, error o exportación puede exponer API keys ni tokens.
5. **Verificación disciplinada:** cada tarea cerrada cumple pruebas de los servicios tocados, `npm test` + `npm run build` (+ Playwright si afecta UI) y `docker compose -f docker/docker-compose.yml config --quiet` cuando toque despliegue.

---

## 2. Fases completadas (resumen depurado)

- **Fase 0 (`R0-01`–`R0-04`) — `terminada`:**
  - `R0-01`: Limpieza de enlaces rotos en `docs/plans/` y enlace de `roadmap.md` en `docs/maintainers.md`.
  - `R0-02`: `Makefile` modernizado para los 11 servicios, frontend y verificación sintética (`bd-final-check`).
  - `R0-03`: Historial de chat unificado leyendo `conversation_messages` con permisos mínimos y fallback legacy a `chat_messages`.
  - `R0-04`: Corpus sintético `S1`–`S5` (`tests/fixtures/eval_corpus/`) y harness reproducible (`scripts/eval/run_eval_baseline.py`).
- **Fase 1 (`R1-01`–`R1-05`) — `terminada`:**
  - `R1-01`: Migración aditiva en `tenant_integrations` (`secrets_encrypted`, `updated_by_user_id`), grants mínimos a `auth_runtime` y `rag_chat_runtime`, y test SQL de permisos/aislamiento.
  - `R1-02`: `SecretsCipher` (`secrets1.`, Fernet + rotación de llaves + rechazo de claves débiles) y permiso Django `manage_ai_settings`.
  - `R1-03`: Endpoints DRF `GET/PATCH /api/integrations/groq/`, `PUT/DELETE /api/integrations/groq/credentials/`, `GET /api/integrations/groq/models/` y `POST /api/integrations/groq/test/` con rate-limit y auditoría sin fugas.
  - `R1-04`: `GroqConfigResolver` dinámico por tenant en `RagDocumentChatServices` (DB → `.env` → `not_configured`), TTL + invalidación por `updated_at`, y `provider_status` tipificado.
  - `R1-05`: Vista web `Configuración IA` (`/settings/ai`), mensajes de degradación honesta en Chat, wiring de `SECRETS_ENCRYPTION_KEY` en Compose y actualización de `README.md`, `.env.example` y `docs/operations.md` (más retirada de planes obsoletos ya ejecutados en `docs/plans/core-rag/`).

---

## 3. Plan activo pendiente

### Fase 2 — Motor RAG híbrido, búsqueda moderna y UX de chat

> Objetivo: dar un salto tangible en precisión de recuperación, velocidad de búsqueda y experiencia de lectura/verificación de respuestas.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R2-01` | `pendiente` | P0 | `RagDocumentEmbeddingServices` | **Chunking estructural y metadatos de página/sección.** Mejorar `CreateDocumentEmbeddings` para trocear respetando límites de secciones, párrafos y oraciones (manteniendo `MAX_CHUNK_SIZE` y `CHUNK_OVERLAP`), y refactorizar `PdfExtractor` / `DocxExtractor` para emitir `metadata.page` y `metadata.section` estructurados en cada chunk. **Done:** tests unitarios y mejora verificable en `S1`–`S2`. |
| `R2-02` | `pendiente` | P0 | `scripts/database/` | **Índices HNSW para pgvector y Full-Text Search (`tsvector` GIN).** Crear migración SQL que reemplace `ivfflat` por `HNSW` (`vector_cosine_ops`) en `document_embeddings` y añada columna generada `content_tsv tsvector` + índice GIN (y trigram para `documents.filename`). **Done:** migración probada en BD limpia y en restauración PostgreSQL (`verify_postgres_upgrade.mjs`). |
| `R2-03` | `pendiente` | P0 | `RagDocumentChatServices`, `DocumentSearchServices` | **Recuperación híbrida (vector + FTS + RRF) y modernización de búsqueda.** Combinar distancia coseno pgvector + `ts_rank_cd` mediante Reciprocal Rank Fusion en `RagDocumentChatServices`, y reemplazar `ILIKE '%query%'` en `DocumentSearchServices` por búsqueda FTS indexada con snippets resaltados (y opción de modo semántico/híbrido). **Done:** mejora demostrada sobre el harness `R0-04` (especialmente códigos, cifras y términos exactos) manteniendo intacto `_apply_access_filter`. |
| `R2-04` | `pendiente` | P0 | `RagDocumentChatServices` | **Blindaje anti prompt-injection y citas estructuradas en chat.** Separar explícitamente el contexto documental con delimitadores de datos no confiables en `GroqLLMProvider`, reforzar `_system_prompt` para prohibir seguir instrucciones embebidas en documentos y exigir referencias verificables `[Fuente N]` sin alucinar información faltante. **Done:** suite adversarial `S4` aprobada con 0 ejecuciones de inyección. |
| `R2-05` | `pendiente` | P1 | `frontend/`, `RagDocumentChatServices` | **Chat con Markdown sanitizado, citas clicables y streaming SSE.** Añadir renderizado Markdown seguro en `Message.tsx` (sin HTML crudo, sanitizado contra XSS), convertir referencias `[Fuente N]` en controles interactivos que resalten/abran el fragmento y página en `SourceList` / vista previa, y habilitar streaming SSE opcional en `/api/v1/chat/ask` con fallback síncrono. **Done:** tests unitarios + Playwright + verificación XSS y accesibilidad. |

---

### Fase 3 — Ingesta idempotente y fuentes Markdown/ZIP (Opción O1)

> Objetivo: soportar colecciones Markdown de primera clase (Obsidian, Logseq, Joplin, repos de documentación) sin acoplarse a software propietario ni romper la portabilidad de Docker. Referencia de diseño: [OBSIDIAN_OPTIONS.md](docs/plans/core-rag/OBSIDIAN_OPTIONS.md).

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R3-01` | `pendiente` | P0 | `RagDocumentEmbeddingServices`, `scripts/database/` | **Idempotencia de carga y metadatos de origen normalizados.** Calcular `content_sha256` al ingerir, soportar cabecera/clave `Idempotency-Key` en `POST /api/v1/documents/upload` para evitar duplicados en reintentos, y estandarizar `metadata.source = {kind, path_rel, sha256, imported_via, batch_id}`. **Done:** subir dos veces con misma clave/hash devuelve el recurso sin duplicar originales ni chunks. |
| `R3-02` | `pendiente` | P1 | `RagDocumentEmbeddingServices` | **Extractor `MarkdownNormalizer`.** Parsear frontmatter YAML (título, `tags`, `aliases`, propiedades) a `metadata` sin contaminar los embeddings, extraer enlaces `[[wikilinks]]`, enlaces `.md` y tags `#etiqueta` como relaciones estructuradas en metadatos, y filtrar archivos internos `.obsidian/`. **Done:** tests sobre vault sintética `S3` verificando extracción limpia y trazabilidad. |
| `R3-03` | `pendiente` | P1 | `RagDocumentEmbeddingServices` | **Importación segura por lote (`.zip` / múltiples `.md`).** Nuevo endpoint de importación por lote con límites defensivos estrictos (tamaño descomprimido máximo, ratio anti zip-bomb, tope de archivos, rechazo de symlinks y `../`), detección de renombres por `content_sha256` y resumen por archivo (`creados`, `reutilizados`, `rechazados`). **Done:** todos los casos maliciosos de `S4` rechazados con error tipificado; 0 duplicados en reimportación. |
| `R3-04` | `pendiente` | P1 | `frontend/` | **UI `Aplicaciones > Importar Markdown / ZIP`.** Añadir tarjeta en `ApplicationsPage` siguiendo el patrón UX de Google Drive: selector de `.zip` o carpeta Markdown, progreso por lote, desglose de creados/reutilizados/rechazados y errores por archivo. **Done:** tests unitarios + Playwright + accesibilidad. |

---

### Fase 4 — Knowledge Studio P0 (Artefactos con Evidencia Verificable)

> Objetivo: transformar conjuntos autorizados de documentos en artefactos reutilizables, versionados, auditables y exportables, con citas ancladas al texto real. Referencias: `docs/plans/knowledge-studio/*`.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R4-01` | `pendiente` | P0 | `scripts/database/` | **Esquema SQL `studio` (colecciones, jobs y artefactos versionados).** Crear esquema independiente `studio.*` con `collections` (referencias `document_id + content_sha256`, sin copiar binarios, visibilidad `private/area/company`), `studio_jobs` (cola `FOR UPDATE SKIP LOCKED`, `operation_key` idempotente, heartbeat, cancelación), `artifacts` + `artifact_versions` + enlaces `artifact_sources` para marcar `STALE` ante modificación/borrado de documentos. **Done:** migración reversible + suite de integridad y cascada de borrado. |
| `R4-02` | `pendiente` | P0 | `backend/` (`KnowledgeStudioServices`), `docker/` | **Backend de Studio + worker ligero sobre PostgreSQL.** Implementar servicio acotado tras feature flag `STUDIO_ENABLED`, reutilizando contratos de identidad/acceso y configuración Groq de Fase 1. Revalidar acceso a **todas** las fuentes antes de encolar y antes de leer/compartir; implementar límites de concurrencia, cuota diaria de tokens y caché por huella `(fuentes@sha, plantilla, modelo, opciones)`. **Done:** Compose base sigue funcionando con `STUDIO_ENABLED=false`; tests de aislamiento multi-tenant y revocación en vuelo (`ACCESS_REVOKED`). |
| `R4-03` | `pendiente` | P0 | `backend/` (`KnowledgeStudioServices`) | **Motor JSON estructurado, validador de groundedness y 4 plantillas P0.** Implementar envelope común `ArtifactContent` en Pydantic v2 con validación estricta de anclaje `quote_text ↔ chunk` (máx. 1 reparación automática), marcado explícito de `inferences[]` y `gaps[]`, y las 4 plantillas P0: (1) Resúmenes (`executive`, `sectioned`, `comparative`), (2) Reportes plantillados (`technical`, `exec_memo`, `study_guide`, `glossary`, `faq`, `minutes`, `risk_analysis`), (3) Tabla de evidencia + CSV con procedencia, (4) Tareas propuestas con estado `proposed/accepted/rejected/done` (solo revisión humana). **Done:** 100 % de hechos citados anclados o etiquetados; 0 auto-ejecuciones externas. |
| `R4-04` | `pendiente` | P0 | `DocumentExportServices` | **Generalizar `DocumentExportServices` por `source_type`.** Extender el registro de renderers para admitir `source_type="studio_artifact"` (PDF y Markdown) sin romper el contrato vigente de `chat_message`, conservando verificación sha256, retención, límites e idempotencia (más descarga CSV segura con procedencia desde Studio). **Done:** 100 % de tests previos de exportación en verde + nuevos tests de exportación de artefactos. |
| `R4-05` | `pendiente` | P0 | `frontend/` | **Interfaz web `/studio` y creación de colecciones desde Biblioteca.** Añadir flujo de colecciones en Biblioteca y página `/studio` (pestañas *Generar* y *Mis artefactos*): progreso por pasos cancelable, previsualización Markdown sanitizada con citas `[n]` clicables hacia el chunk original, badges ámbar/gris (`inferencia` / `sin fuente`), editor ligero Markdown que marca citas `detached` si pierden anclaje, versionado, exportación y degradación honesta sin Groq. **Done:** `npm test`, `npm run build`, Playwright + axe aprobados. |
| `R4-06` | `pendiente` | P0 | `scripts/`, `.github/workflows/` | **Gate de evaluación y seguridad de Studio en CI.** Ejecutar el harness `S1`–`S5` sobre las 4 plantillas P0 midiendo groundedness (≥ 95 %), fidelidad numérica (100 % o `unverified`), cero prompt-injection (`S4`), cero fugas multi-tenant y cero secretos en logs/exports. **Done:** reporte JSON versionable en `.release-reports/` y gate automático en CI antes de habilitar Studio por defecto. |

---

### Fase 5 — Hardening de seguridad y extensiones P1+ bajo demanda

> Objetivo: reforzar el despliegue más allá de loopback local y evaluar ampliaciones de Studio solo cuando Fases 2–4 estén validadas en uso real.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R5-01` | `pendiente` | P1 | `AuthServices`, `frontend/`, `docker/` | **Migración de sesión web a cookies `HttpOnly` + protección CSRF.** Retirar tokens de acceso/refresco del almacenamiento del navegador (deuda documentada en `frontend/AUDIT.md`), coordinando CORS, cookies `SameSite` y renovación silenciosa entre Auth, Nginx y Frontend. **Done:** login/refresh/logout y suite de verificación de instalación aprobados sin tokens en storage JS. |
| `R5-02` | `pendiente` | P1 | `AuthServices`, `scripts/database/`, `frontend/` | **Activar `audit_logs` persistente y visor administrativo de auditoría.** Aprovechar la tabla `audit_logs` (`011_notifications_audit.sql`) para registrar acciones administrativas críticas (cambios de IA, permisos, borrados documentales, exportaciones y eventos Studio) con consulta filtrable para `TENANT_ADMIN`/superadmin, siempre sin payloads sensibles. **Done:** registro persistente + paginación + test de no-exposición de secretos. |
| `R5-03` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Visualizaciones deterministas en Studio (P1).** Mapas conceptuales interactivos alimentados por `[[wikilinks]]`/evidencia (`reactflow`), diagramas Mermaid con `securityLevel: 'strict'` y gráficos numéricos generados **exclusivamente** desde celdas verificadas de una `evidence_table`. **Done:** render sanitizado en cliente, cero valores inventados y export SVG/PNG. |
| `R5-04` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Quizzes y flashcards locales con verificación de citas (P1).** Generación validada (única respuesta correcta + explicación citada; descarte automático de preguntas inválidas) y práctica local offline con repaso espaciado simple (SM-2 sin telemetría). **Done:** 100 % de preguntas válidas tras validador y práctica offline funcional sin Groq. |
| `R5-05` | `pendiente` | P2 | `docs/`, `backend/` | **ADR de extensibilidad: proveedores OpenAI-compatible/Ollama y MCP de solo lectura.** Definir ADR formal antes de código para (a) nuevos adaptadores sobre el puerto `LLMProvider` (incluyendo allowlist SSRF y perfil Compose opcional para Ollama) y (b) superficie MCP de solo lectura autenticada siempre con el token del usuario de la plataforma. **Done:** ADR aprobado y validado contra el modelo de amenazas antes de iniciar implementación. |

---

## 4. Fuera de alcance (descartado explícitamente en esta etapa)

- **Conector nativo de Obsidian con bind-mounts / file watchers (O2) ni sincronización bidireccional.**
- **Video-resúmenes, infografías generadas por IA de imágenes y Audio Overviews/TTS en el stack base.**
- **Deep Research multi-paso sin presupuesto ni alcance cerrado.**
- **Sharing público anónimo por enlace.**
- **Infraestructura adicional pesada (Redis, Celery, RabbitMQ, Elasticsearch).**
- **Auto-ejecución de tareas en gestores externos sin confirmación humana.**
