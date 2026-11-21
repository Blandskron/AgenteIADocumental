# Roadmap de Evolución — Blandskron Documental (Etapa 2)

> Documento vivo de ejecución para llevar **Blandskron Documental** al siguiente nivel: de una aplicación RAG local sólida a una plataforma documental inteligente, configurable desde la web, con recuperación híbrida de alta precisión y generación de artefactos verificables con evidencia.

**Fecha de creación:** 2026-11-21  
**Base auditada:** rama `rag-core-evolution-audit-6ac6c` (sobre `main` `055a85d`)  
**Fuentes contrastadas:** `docs/plans/core-rag/*`, `docs/plans/knowledge-studio/*`, arquitectura, esquemas SQL, 11 servicios backend y frontend React/TypeScript.

---

## Convención de estados

Todas las tareas de este roadmap se marcan exclusivamente con uno de estos tres estados:

- `pendiente` — Planificada y lista para priorizar o iniciar.
- `en progreso` — En desarrollo o verificación activa.
- `terminada` — Implementada, probada y validada según los criterios de cierre del repositorio (`AGENTS.md`).

---

## Resumen de avance

| Fase | Enfoque | Total | Pendiente | En progreso | Terminada |
| --- | --- | ---: | ---: | ---: | ---: |
| **Fase 0** | Higiene técnica, historial único y base de evaluación | 4 | 0 | 0 | 4 |
| **Fase 1** | Configuración de IA (Groq) desde la web y degradación honesta | 5 | 1 | 0 | 4 |
| **Fase 2** | Motor RAG híbrido, búsqueda moderna y UX de chat | 5 | 5 | 0 | 0 |
| **Fase 3** | Ingesta idempotente y fuentes Markdown/ZIP (Opción O1) | 4 | 4 | 0 | 0 |
| **Fase 4** | Knowledge Studio P0 (artefactos con citas verificadas) | 6 | 6 | 0 | 0 |
| **Fase 5** | Hardening de seguridad y extensiones P1+ bajo demanda | 5 | 5 | 0 | 0 |
| **Total** | | **29** | **21** | **0** | **8** |

---

## 1. Contraste: `docs/plans/` frente al repositorio real

### 1.1 Veredicto sobre los documentos en `docs/plans/`

| Documento en `docs/plans/` | Diagnóstico tras contrastar con el código | Decisión |
| --- | --- | --- |
| `core-rag/CURRENT_STATE_AUDIT.md` | Muy preciso. Confirma los 11 servicios, E5 local (384 dims, ya usa correctamente prefijos `passage:` / `query:`), `tenant_integrations` sin consumidor, `TokenCipher` en Drive y fallback opaco de Groq. | **Base válida.** Corregir referencias rotas a archivos inexistentes (`GRAPHRAG_EVALUATION.md`, `BACKLOG.md`, `PROMPT 3`). |
| `core-rag/GROQ_SETTINGS_DESIGN.md` | **Alto valor inmediato.** Aprovecha la tabla `tenant_integrations` ya existente (`011_notifications_audit.sql`) y el patrón `TokenCipher` de Drive para configurar Groq sin tocar `.env` ni reiniciar contenedores. Nota real del código: los permisos se siembran en migraciones Django de `AuthServices` (`001_reference_data.sql`), no en SQL seeds. | **Adoptar en Fase 1.** |
| `core-rag/OBSIDIAN_OPTIONS.md` | Análisis realista: Obsidian no tiene API oficial y hoy `PlainTextExtractor` solo ingiere `.md` como texto plano sin frontmatter ni wikilinks. | **Adoptar solo Opción O1** (Markdown/ZIP genérico con idempotencia por hash) en **Fase 3**. Descartar O2 (conector nativo/bind-mounts). |
| `knowledge-studio/PRODUCT_SPEC.md` y `FEATURE_BENCHMARK.md` | Resuelve una brecha real de producto: pasar de respuestas sueltas a artefactos reutilizables con citas. Sin embargo, plantea demasiados tipos de artefacto (11) y funcionalidades secundarias (slides, audio, deep research) para un solo salto. | **Adoptar solo P0 (4 artefactos + colecciones)** en **Fase 4**. Posponer P1 a Fase 5 y descartar multimedia/video. |
| `knowledge-studio/ARCHITECTURE_ADR.md` y `ARTIFACT_SCHEMAS.md` | Buenas decisiones técnicas: cola ligera en PostgreSQL (`FOR UPDATE SKIP LOCKED`, cero Redis/Celery), JSON estructurado con validación de citas y reutilización de `DocumentExportServices`. Riesgo: añadir un 12.º microservicio antes de madurar el núcleo RAG añade fricción operativa. | **Adoptar diseño de datos, cola PG y validación estricta** en **Fase 4**, después de fortalecer el núcleo en Fases 0–3. |
| `knowledge-studio/EVALUATION_PLAN.md` | Excelente enfoque de corpus sintético (`S1`–`S5`, con `S4-adversarial`) para medir groundedness, seguridad y regresión en CI. | **Adelantar la base del corpus (`S1`–`S5`) a Fase 0** para medir mejoras RAG desde el inicio y reutilizarlo en Studio. |

### 1.2 Brechas críticas detectadas en el repositorio (no cubiertas por `docs/plans/`)

Al revisar directamente el código fuente y los esquemas SQL, aparecieron mejoras estructurales que tienen impacto inmediato en calidad, rendimiento y UX:

1. **Índice vectorial subóptimo (`scripts/database/indexes/001_indexes.sql`):** `document_embeddings` usa `ivfflat (lists = 100)` creado sobre tabla vacía al inicializar; esto degrada el recall en bases pequeñas y medias. Migrar a **HNSW** mejora recall y latencia desde el primer documento.
2. **Búsqueda únicamente léxica con `ILIKE '%query%'` (`DocumentSearchServices`):** `document_search_repository_pg.py` hace escaneos `ILIKE` sobre `chunk_content` y `filename` sin índice Full-Text (`tsvector`) ni recuperación semántica/híbrida.
3. **Chunking por ventana fija de caracteres (`RagDocumentEmbeddingServices`):** `create_document_embeddings.py` corta texto de forma rígida por `start:end`, partiendo oraciones/párrafos y dejando el marcador `[page N]` de `pdf_extractor.py` mezclado en texto plano en lugar de estructurarlo en `metadata.page`.
4. **Chat sin Markdown sanitizado, sin citas clicables y sin streaming (`frontend/src/features/chat/ui/Message.tsx`):** las respuestas se renderizan como texto plano, las fuentes solo muestran `<details>` crudos y el usuario espera la respuesta completa de Groq sin streaming.
5. **Prompt RAG vulnerable a inyección documental (`llm_provider_groq.py`):** el contexto recuperado se interpola sin delimitadores estrictos `system`/`data` ni directiva anti-inyección, y el prompt actual invita a inferir sin anclaje explícito.
6. **Doble historial de chat (`scripts/database/schemas/002_conversations.sql`):** coexisten `chat_messages` (usada por `RagDocumentChatServices`) y `conversation_messages` (usada por `ConversationServices`). Conviene unificar antes de construir Studio.
7. **Subida sin idempotencia (`RagDocumentEmbeddingServices`):** reintentos de upload duplican documentos y chunks.
8. **Higiene y deuda operativa:** `Makefile` solo cubre 4 de los 11 servicios; `audit_logs` existe en BD sin uso transversal; y los tokens de sesión web aún viven en almacenamiento del navegador (riesgo ya documentado en `frontend/AUDIT.md`).

---

## 2. Invariantes de arquitectura (reglas no negociables)

1. **Independencia de embeddings locales:** `intfloat/multilingual-e5-small` en CPU (`local_files_only=True`) jamás depende de Groq ni de conectividad externa; revocar o romper la clave LLM nunca puede afectar ingesta, búsqueda ni biblioteca.
2. **Autorización antes de recuperar:** todo filtro multi-tenant (propietario, asignaciones, área, grupos, `TENANT_ADMIN`) se ejecuta en el servidor antes de recuperar fragmentos o enviar contexto al LLM.
3. **Despliegue local simple:** `docker compose up` debe seguir funcionando sin añadir Redis, Celery, Elasticsearch ni GPU en el stack base.
4. **Cero secretos y datos reales:** toda prueba, benchmark o fixture usa documentos y credenciales 100% sintéticas; ningún log, error o exportación puede exponer API keys ni tokens.
5. **Verificación disciplinada:** cada tarea cerrada cumple pruebas unitarias/integración de los servicios tocados, `npm test` + `npm run build` (+ Playwright si afecta UI) y `docker compose -f docker/docker-compose.yml config --quiet` cuando toque despliegue.

---

## 3. Plan de tareas ejecutable

### Fase 0 — Higiene técnica, historial único y base de evaluación

> Objetivo: ordenar la casa, eliminar deuda que bloquearía las siguientes fases y crear el banco de pruebas sintético para medir mejoras reales.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R0-01` | `terminada` | P0 | `docs/plans/`, `docs/` | **Depurar referencias rotas en `docs/plans/` y enlazar `roadmap.md`.** Anotar explícitamente el estado histórico/propuesta de los planes, eliminar o marcar enlaces rotos (`GRAPHRAG_EVALUATION.md`, `BACKLOG.md`, `PROMPT 3`) y referenciar `roadmap.md` desde `docs/maintainers.md`. **Done:** cero enlaces rotos en `docs/`. |
| `R0-02` | `terminada` | P1 | `Makefile`, `docs/operations.md` | **Actualizar `Makefile` para reflejar los 11 servicios y el flujo real de desarrollo/verificación.** Incorporar targets coherentes con `docker/docker-compose.yml`, lint/test por servicio y verificación sintética (`bd-final-check`). **Done:** targets probados y alineados con `docs/operations.md`. |
| `R0-03` | `terminada` | P0 | `RagDocumentChatServices`, `ConversationServices`, `scripts/database/` | **Consolidar fuente de verdad del historial de chat.** Evaluar y migrar la lectura de contexto conversacional de `RagDocumentChatServices` hacia `conversation_messages` (con permiso de lectura acotado al propietario y compatibilidad hacia atrás con `chat_messages` si existen datos previos). **Done:** una sola fuente de historial verificada con tests de aislamiento por usuario. |
| `R0-04` | `terminada` | P0 | `scripts/`, `tests/fixtures/` | **Crear corpus sintético de evaluación (`S1`–`S5`) y harness reproducible.** Incluir acta sintética (`S1`), informes numéricos comparativos (`S2`), notas Markdown con wikilinks (`S3`), casos adversariales de prompt-injection/path-traversal/zip-bomb (`S4`) y ruido OCR (`S5`), más script en `scripts/` que ejecute métricas base y emita reporte JSON en `.release-reports/`. **Done:** línea base medida y repetible sin datos personales. |

---

### Fase 1 — Configuración de IA (Groq) desde la web y degradación honesta

> Objetivo: permitir que un administrador configure, pruebe, cambie y revoque Groq desde la UI sin editar `.env` ni reiniciar contenedores, manteniendo el modo local intacto.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R1-01` | `terminada` | P0 | `scripts/database/` | **Migración SQL aditiva en `tenant_integrations` y permisos de roles.** Añadir columnas `secrets_encrypted TEXT` y `updated_by_user_id TEXT`, mantener compatibilidad reversible y otorgar privilegios mínimos a `auth` (escritura/lectura) y `rag_chat_runtime` (solo lectura de fila activa). **Done:** migración idempotente + test SQL de permisos y aislamiento multi-tenant. |
| `R1-02` | `terminada` | P0 | `AuthServices`, `GoogleDriveImportServices` | **Cifrado autenticado en reposo (`secrets1.`) y permiso `manage_ai_settings`.** Reutilizar el patrón `TokenCipher` (Fernet + llavero versionado con `SECRETS_ENCRYPTION_KEY`, `SECRETS_KEY_ID`, `SECRETS_PREVIOUS_KEYS`, rechazo de secretos de ejemplo) y crear migración Django en `AuthServices` para sembrar el permiso `manage_ai_settings` (asignable a `TENANT_ADMIN`, implícito en superadmin `*`). **Done:** tests de cifrado, rotación, rechazo de clave débil y autorización. |
| `R1-03` | `terminada` | P0 | `AuthServices` | **Endpoints DRF de gestión y prueba de Groq.** Implementar `GET/PATCH /api/integrations/groq/`, `PUT/DELETE /api/integrations/groq/credentials/`, `GET /api/integrations/groq/models/` y `POST /api/integrations/groq/test/` (validación real mínima de 1 token sin datos documentales, timeout 10s, rate-limit por usuario, huella SHA-256 corta sin exponer nunca la clave, auditoría estructurada). **Done:** suite DRF con pruebas de autorización 403 cross-tenant, rate-limit y cero fugas en respuestas/logs. |
| `R1-04` | `terminada` | P0 | `RagDocumentChatServices` | **Resolución dinámica de credenciales Groq y estados explícitos de proveedor.** Reemplazar el `lru_cache` rígido del proveedor LLM por resolución por petición con TTL corto (30–60s) e invalidación por `updated_at`: precedencia DB (`tenant_integrations`) → `.env` → `not_configured`. Propagar estados tipificados (`ok`, `not_configured`, `auth_error`, `rate_limited`, `provider_error`) en lugar del fallback opaco. **Done:** tests con proveedor simulado, prueba de cambio en caliente sin reinicio y test de regresión que demuestra independencia total de `LocalEmbeddingProvider`. |
| `R1-05` | `pendiente` | P0 | `frontend/`, `docs/` | **Vista `Configuración > IA` (`/settings/ai`) y banner de estado en Chat.** Crear feature `features/settings-ai` visible solo con `manage_ai_settings` (formulario sin `localStorage`, huella corta, selector de modelos desde backend, botón Probar conexión, Revocar, bloque informativo de E5 local) y mejorar mensajes de chat cuando el proveedor no está configurado o está limitado. Actualizar `README.md`, `.env.example` y `docs/operations.md`. **Done:** `npm test`, `npm run build` y pruebas Playwright con mocks en temas claro/oscuro y verificación de accesibilidad axe. |

---

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

> Objetivo: soportar colecciones Markdown de primera clase (Obsidian, Logseq, Joplin, repos de documentación) sin acoplarse a software propietario ni romper la portabilidad de Docker.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R3-01` | `pendiente` | P0 | `RagDocumentEmbeddingServices`, `scripts/database/` | **Idempotencia de carga y metadatos de origen normalizados.** Calcular `content_sha256` al ingerir, soportar cabecera/clave `Idempotency-Key` en `POST /api/v1/documents/upload` para evitar duplicados en reintentos, y estandarizar `metadata.source = {kind, path_rel, sha256, imported_via, batch_id}`. **Done:** subir dos veces con misma clave/hash devuelve el recurso sin duplicar originales ni chunks. |
| `R3-02` | `pendiente` | P1 | `RagDocumentEmbeddingServices` | **Extractor `MarkdownNormalizer`.** Parsear frontmatter YAML (título, `tags`, `aliases`, propiedades) a `metadata` sin contaminar los embeddings, extraer enlaces `[[wikilinks]]`, enlaces `.md` y tags `#etiqueta` como relaciones estructuradas en metadatos, y filtrar archivos internos `.obsidian/`. **Done:** tests sobre vault sintética `S3` verificando extracción limpia y trazabilidad. |
| `R3-03` | `pendiente` | P1 | `RagDocumentEmbeddingServices` | **Importación segura por lote (`.zip` / múltiples `.md`).** Nuevo endpoint de importación por lote con límites defensivos estrictos (tamaño descomprimido máximo, ratio anti zip-bomb, tope de archivos, rechazo de symlinks y `../`), detección de renombres por `content_sha256` y resumen por archivo (`creados`, `reutilizados`, `rechazados`). **Done:** todos los casos maliciosos de `S4` rechazados con error tipificado; 0 duplicados en reimportación. |
| `R3-04` | `pendiente` | P1 | `frontend/` | **UI `Aplicaciones > Importar Markdown / ZIP`.** Añadir tarjeta en `ApplicationsPage` siguiendo el patrón UX de Google Drive: selector de `.zip` o carpeta Markdown, progreso por lote, desglose de creados/reutilizados/rechazados y errores por archivo. **Done:** tests unitarios + Playwright + accesibilidad. |

---

### Fase 4 — Knowledge Studio P0 (Artefactos con Evidencia Verificable)

> Objetivo: transformar conjuntos autorizados de documentos en artefactos reutilizables, versionados, auditables y exportables, con citas ancladas al texto real.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R4-01` | `pendiente` | P0 | `scripts/database/` | **Esquema SQL `studio` (colecciones, jobs y artefactos versionados).** Crear esquema independiente `studio.*` con `collections` (referencias `document_id + content_sha256`, sin copiar binarios, visibilidad `private/area/company`), `studio_jobs` (cola `FOR UPDATE SKIP LOCKED`, `operation_key` idempotente, heartbeat, cancelación), `artifacts` + `artifact_versions` + enlaces `artifact_sources` para marcar `STALE` ante modificación/borrado de documentos. **Done:** migración reversible + suite de integridad y cascada de borrado. |
| `R4-02` | `pendiente` | P0 | `backend/` (`KnowledgeStudioServices`), `docker/` | **Backend de Studio + worker ligero sobre PostgreSQL.** Implementar servicio acotado tras feature flag `STUDIO_ENABLED`, reutilizando contratos de identidad/acceso y configuración Groq de Fase 1. Revalidar acceso a **todas** las fuentes antes de encolar y antes de leer/compartir; implementar límites de concurrencia, cuota diaria de tokens y caché por huella `(fuentes@sha, plantilla, modelo, opciones)`. **Done:** Compose base sigue funcionando con `STUDIO_ENABLED=false`; tests de aislamiento multi-tenant y revocación en vuelo (`ACCESS_REVOKED`). |
| `R4-03` | `pendiente` | P0 | `backend/` (`KnowledgeStudioServices`) | **Motor JSON estructurado, validador de groundedness y 4 plantillas P0.** Implementar envelope común `ArtifactContent` en Pydantic v2 con validación estricta de anclaje `quote_text ↔ chunk` (máx. 1 reparación automática), marcado explícito de `inferences[]` y `gaps[]`, y las 4 plantillas P0: (1) Resúmenes (`executive`, `sectioned`, `comparative`), (2) Reportes plantillados (`technical`, `exec_memo`, `study_guide`, `glossary`, `faq`, `minutes`, `risk_analysis`), (3) Tabla de evidencia + CSV con procedencia, (4) Tareas propuestas con estado `proposed/accepted/rejected/done` (solo revisión humana). **Done:** 100% de hechos citados anclados o etiquetados; 0 auto-ejecuciones externas. |
| `R4-04` | `pendiente` | P0 | `DocumentExportServices` | **Generalizar `DocumentExportServices` por `source_type`.** Extender el registro de renderers para admitir `source_type="studio_artifact"` (PDF y Markdown) sin romper el contrato vigente de `chat_message`, conservando verificación sha256, retención, límites e idempotencia (más descarga CSV segura con procedencia desde Studio). **Done:** 100% de tests previos de exportación en verde + nuevos tests de exportación de artefactos. |
| `R4-05` | `pendiente` | P0 | `frontend/` | **Interfaz web `/studio` y creación de colecciones desde Biblioteca.** Añadir flujo de colecciones en Biblioteca y página `/studio` (pestañas *Generar* y *Mis artefactos*): progreso por pasos cancelable, previsualización Markdown sanitizada con citas `[n]` clicables hacia el chunk original, badges ámbar/gris (`inferencia` / `sin fuente`), editor ligero Markdown que marca citas `detached` si pierden anclaje, versionado, exportación y degradación honesta sin Groq. **Done:** `npm test`, `npm run build`, Playwright + axe aprobados. |
| `R4-06` | `pendiente` | P0 | `scripts/`, `.github/workflows/` | **Gate de evaluación y seguridad de Studio en CI.** Ejecutar el harness `S1`–`S5` sobre las 4 plantillas P0 midiendo groundedness (≥ 95%), fidelidad numérica (100% o `unverified`), cero prompt-injection (`S4`), cero fugas multi-tenant y cero secretos en logs/exports. **Done:** reporte JSON versionable en `.release-reports/` y gate automático en CI antes de habilitar Studio por defecto. |

---

### Fase 5 — Hardening de seguridad y extensiones P1+ bajo demanda

> Objetivo: reforzar el despliegue más allá de loopback local y evaluar ampliaciones de Studio solo cuando Fase 0–4 estén validadas en uso real.

| ID | Estado | Prioridad | Ámbito | Tarea y criterio de terminado |
| --- | --- | --- | --- | --- |
| `R5-01` | `pendiente` | P1 | `AuthServices`, `frontend/`, `docker/` | **Migración de sesión web a cookies `HttpOnly` + protección CSRF.** Retirar tokens de acceso/refresco del almacenamiento del navegador (deuda documentada en `frontend/AUDIT.md`), coordinando CORS, cookies `SameSite` y renovación silenciosa entre Auth, Nginx y Frontend. **Done:** login/refresh/logout y suite de verificación de instalación aprobados sin tokens en storage JS. |
| `R5-02` | `pendiente` | P1 | `AuthServices`, `scripts/database/`, `frontend/` | **Activar `audit_logs` persistente y visor administrativo de auditoría.** Aprovechar la tabla `audit_logs` (`011_notifications_audit.sql`) para registrar acciones administrativas críticas (cambios de IA, permisos, borrados documentales, exportaciones y eventos Studio) con consulta filtrable para `TENANT_ADMIN`/superadmin, siempre sin payloads sensibles. **Done:** registro persistente + paginación + test de no-exposición de secretos. |
| `R5-03` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Visualizaciones deterministas en Studio (P1).** Mapas conceptuales interactivos alimentados por `[[wikilinks]]`/evidencia (`reactflow`), diagramas Mermaid con `securityLevel: 'strict'` y gráficos numéricos generados **exclusivamente** desde celdas verificadas de una `evidence_table`. **Done:** render sanitizado en cliente, cero valores inventados y export SVG/PNG. |
| `R5-04` | `pendiente` | P2 | `frontend/`, `KnowledgeStudioServices` | **Quizzes y flashcards locales con verificación de citas (P1).** Generación validada (única respuesta correcta + explicación citada; descarte automático de preguntas inválidas) y práctica local offline con repaso espaciado simple (SM-2 sin telemetría). **Done:** 100% de preguntas válidas tras validador y práctica offline funcional sin Groq. |
| `R5-05` | `pendiente` | P2 | `docs/`, `backend/` | **ADR de extensibilidad: proveedores OpenAI-compatible/Ollama y MCP de solo lectura.** Definir ADR formal antes de código para (a) nuevos adaptadores sobre el puerto `LLMProvider` (incluyendo allowlist SSRF y perfil Compose opcional para Ollama) y (b) superficie MCP de solo lectura autenticada siempre con el token del usuario de la plataforma. **Done:** ADR aprobado y validado contra el modelo de amenazas antes de iniciar implementación. |

---

## 4. Fuera de alcance (descartado explícitamente en esta etapa)

Para proteger el foco, el coste operativo y la calidad de ingeniería, **no** se incluirán en este roadmap:

- **Conector nativo de Obsidian con bind-mounts / file watchers (O2) ni sincronización bidireccional:** fragilidad multi-SO en Docker, riesgo de corromper bóvedas locales y ausencia de API oficial de Obsidian.
- **Video-resúmenes, infografías generadas por IA de imágenes y Audio Overviews/TTS en el stack base:** alto coste de modelos/licencias/GPU para valor marginal frente al núcleo documental.
- **Deep Research multi-paso sin presupuesto ni alcance cerrado:** coste impredecible de tokens y alto riesgo de alucinación.
- **Sharing público anónimo por enlace:** contradice el modelo de aislamiento multi-tenant y revalidación de permisos.
- **Infraestructura adicional pesada (Redis, Celery, RabbitMQ, Elasticsearch):** innecesaria mientras PostgreSQL 16 + pgvector + HNSW + FTS + `SKIP LOCKED` cubran con holgura el volumen objetivo.
- **Auto-ejecución de tareas en gestores externos:** cualquier acción externa futura requerirá confirmación humana explícita y auditoría.

---

## 5. Orden recomendado de ejecución inmediata

Para empezar a avanzar hoy con entregas pequeñas, verificables y de máximo impacto:

1. **Bloque A (cimientos):** `R0-01` → `R0-03` → `R0-04` (limpieza de docs, historial unificado y corpus de evaluación).
2. **Bloque B (IA configurable desde la web):** `R1-01` → `R1-02` → `R1-03` → `R1-04` → `R1-05`.
3. **Bloque C (salto de calidad RAG y UX):** `R2-01` → `R2-02` → `R2-03` → `R2-04` → `R2-05`.
4. **Bloque D (Markdown/ZIP e idempotencia):** `R3-01` → `R3-02` → `R3-03` → `R3-04`.
5. **Bloque E (Knowledge Studio P0):** `R4-01` → `R4-02` → `R4-03` → `R4-04` → `R4-05` → `R4-06`.
6. **Bloque F (hardening y P1+):** `R5-01` → `R5-02` y evaluación de `R5-03`..`R5-05`.

