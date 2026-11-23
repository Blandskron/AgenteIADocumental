# 02 — Investigación de Capacidades Funcionales del Ecosistema

- **Alcance:** Análisis técnico y funcional de las capacidades relevantes en plataformas modernas de inteligencia documental, gestión del conocimiento, búsqueda empresarial, RAG, investigación asistida y automatización local.
- **Principio metodológico:** Cada capacidad se estudia exclusivamente por el problema que resuelve, su valor operativo, sus enfoques técnicos open source y su viabilidad en operación **100 % gratuita, local-first y sin dependencias cloud obligatorias**.
- **Commit base de contraste:** `develop@5a4fac2` (22 de noviembre de 2026).

---

## 1. Gestión documental

### 1.1 Organización de bibliotecas, carpetas compartidas y espacios de trabajo
1. **Problema:** Los usuarios y equipos necesitan estructurar cientos o miles de documentos más allá de una lista plana, separando archivos privados de repositorios departamentales.
2. **Valor:** Reduce el tiempo de localización y permite acotar búsquedas y sesiones de chat a un contexto curado.
3. **Enfoques técnicos:** Árbol jerárquico en PostgreSQL (`parent_folder_id` con CTE recursiva), visibilidad `PRIVATE` vs `TENANT`/`AREA` gobernada por RBAC existente.
4. **Limitaciones:** Las jerarquías estrictas fuerzan una única ubicación por archivo si no se combinan con etiquetas o colecciones.
5. **100 % local:** Sí.
6. **Dependencias:** PostgreSQL 16 (ya existente).
7. **Consumo de recursos:** Despreciable (<10 MB RAM, índices B-Tree).
8. **¿Existe en el proyecto?:** Parcialmente (`DocumentLibraryServices` ofrece carpetas privadas, favoritos y recientes; no hay carpetas compartidas ni navegación de subcarpetas en UI).
9. **Reutilización:** Ampliar `document_folders` y `DocumentLibraryServices` sin crear servicios nuevos.
10. **¿Justifica incorporación?:** Sí (P1) para subcarpetas en UI y carpetas compartidas por área/tenant.

### 1.2 Etiquetas (tags), metadatos editables y colecciones de investigación
1. **Problema:** Un mismo documento puede pertenecer a varios ejes (p. ej. `contrato`, `fiscal-2026`, `urgente`) y necesitar metadatos estructurados editables después de la subida.
2. **Valor:** Permite filtrado transversal en búsqueda, chat RAG y automatizaciones sin duplicar archivos.
3. **Enfoques técnicos:** Tablas relacionales `document_tags` / `tags` por tenant con índice GIN/B-Tree, más reutilización de `studio.collections` y `studio.collection_documents` para cuadernos de investigación.
4. **Limitaciones:** Requiere control de taxonomía para evitar proliferación de etiquetas inconsistentes.
5. **100 % local:** Sí.
6. **Dependencias:** PostgreSQL 16.
7. **Consumo de recursos:** Despreciable.
8. **¿Existe en el proyecto?:** No encontrado para tags/metadatos editables; `studio.collections` existe en esquema pero `collection_documents` no tiene endpoints.
9. **Reutilización:** `DocumentLibraryServices` (tags/metadatos) + `KnowledgeStudioServices` (`collection_documents`).
10. **¿Justifica incorporación?:** Sí (P1).

### 1.3 Versionado documental y ciclo de vida (retención / archivo)
1. **Problema:** Cuando cambia un contrato, política o manual, re-subirlo hoy crea un duplicado o destruye el historial previo; además, documentos expirados permanecen activos indefinidamente.
2. **Valor:** Trazabilidad histórica, comparación exacta entre versiones (`v1` vs `v2`) y cumplimiento de políticas de retención.
3. **Enfoques técnicos:** Tabla `document_versions` vinculada a `documents` con `version_number`, `content_sha256`, `storage_path`, `is_current`; estado `ARCHIVED` y tarea periódica local de evaluación de `expires_at`.
4. **Limitaciones:** Aumenta almacenamiento en disco si se conservan todos los binarios históricos sin límite configurable.
5. **100 % local:** Sí.
6. **Dependencias:** PostgreSQL 16 + almacenamiento local de archivos.
7. **Consumo de recursos:** Disco proporcional a versiones retenidas; CPU/RAM mínimos.
8. **¿Existe en el proyecto?:** No encontrado (`documents.expires_at` existe en tabla pero no se procesa; reindexar reemplaza chunks sin historial).
9. **Reutilización:** `RagDocumentEmbeddingServices` + `DocumentAccessServices` + `scripts/database/`.
10. **¿Justifica incorporación?:** Sí (P1/P2), indispensable para comparación documental real y trazabilidad de citas.

### 1.4 Permisos, auditoría y colaboración
1. **Problema:** Equipos y pymes requieren control granular de quién ve, descarga o aprueba documentos, con trazabilidad inmutable.
2. **Valor:** Cumplimiento interno, aislamiento multiempresa y evidencia verificable de acciones.
3. **Enfoques técnicos:** RBAC por tenant/área/grupo + asignaciones con workflow + `audit_logs` paginados y exportables.
4. **Limitaciones:** Sin RLS nativo de PostgreSQL, cada servicio debe mantener filtros SQL sincronizados.
5. **100 % local:** Sí.
6. **Dependencias:** PostgreSQL 16 + `AuthServices`.
7. **Consumo de recursos:** Muy bajo.
8. **¿Existe en el proyecto?:** Implementado en el núcleo (`AuthServices`, `DocumentAccessServices`, `audit_logs`); brechas en `AuditLogsPage` (sin paginación/exportación) y bug en `AgentOrchestratorServices/AuditLogger`.
9. **Reutilización:** Reparar `AuditLogger` y completar `AuditLogsPage`.
10. **¿Justifica incorporación?:** Sí (P0 para reparación de auditoría de agentes; P1 para filtros/exportación UI).

---

## 2. Procesamiento documental

### 2.1 OCR multilingüe y detección automática de PDFs escaneados
1. **Problema:** Gran parte de contratos, facturas y actas en entornos reales son PDFs escaneados (imagen dentro de PDF) en español o bilingües. Hoy `PdfExtractor` falla si la capa de texto está vacía y Tesseract Docker solo tiene `eng.traineddata`.
2. **Valor:** Desbloquea el uso real con documentos escaneados en español sin depender de servicios OCR en la nube.
3. **Enfoques técnicos:** Añadir `spa.traineddata` a Tesseract 5.5.4 + detección automática de páginas con densidad textual baja (`< N` chars) + renderizado a imagen (`pypdfium2` Apache-2.0 o `pdf2image`/`poppler`) + OCR por página; alternativa avanzada opcional: PaddleOCR (Apache-2.0).
4. **Limitaciones:** OCR en CPU consume 1–4 s por página; documentos de >50 páginas escaneadas requieren procesamiento asíncrono para no agotar timeouts HTTP.
5. **100 % local:** Sí.
6. **Dependencias:** `tesseract-ocr-spa` (Apache-2.0) + `pypdfium2` (Apache-2.0/BSD).
7. **Consumo de recursos:** ~200–500 MB RAM pico por página rasterizada; CPU intensivo durante ingesta.
8. **¿Existe en el proyecto?:** Parcialmente (OCR solo para PNG/JPEG/TIFF en inglés; nulo para PDFs escaneados).
9. **Reutilización:** `RagDocumentEmbeddingServices` (`PdfExtractor` + `ImageOcrExtractor`).
10. **¿Justifica incorporación?:** Sí (P0/P1) — impacto inmediato en usabilidad en español.

### 2.2 Parsing estructural, conservación de tablas y formatos ofimáticos (XLSX/PPTX/HTML)
1. **Problema:** Extraer texto plano con `pypdf` o mover tablas DOCX al final destruye filas, columnas y encabezados de estados financieros, anexos y matrices; tampoco se soportan XLSX ni PPTX.
2. **Valor:** Mejora drásticamente la precisión de RAG y extracción de montos/fechas sobre tablas reales.
3. **Enfoques técnicos:**
   - **Nivel ligero (CPU bajo):** `pdfplumber` (MIT) para tablas PDF, iteración en orden de documento en `python-docx`, `openpyxl` (MIT) para XLSX y `python-pptx` (MIT) para PPTX, normalizando tablas a Markdown válido.
   - **Nivel avanzado opcional:** `Docling` (MIT, layout + TableFormer) en perfil opcional o worker dedicado para equipos con ≥8 GB RAM.
4. **Limitaciones:** `Docling` descarga pesos de layout (~500 MB–1 GB) y consume más RAM/CPU; `PyMuPDF4LLM` tiene licencia AGPL-3.0 (incompatible con MIT sin cambio de licencia, por lo que **se descarta**).
5. **100 % local:** Sí.
6. **Dependencias:** `pdfplumber` (MIT), `openpyxl` (MIT), `python-pptx` (MIT); opcional `docling` (MIT).
7. **Consumo de recursos:** Nivel ligero: <150 MB RAM extra. Nivel `Docling`: +1.5–2.5 GB RAM en ingesta.
8. **¿Existe en el proyecto?:** Parcialmente (PDF texto plano, DOCX con tablas desordenadas, CSV plano, sin XLSX/PPTX).
9. **Reutilización:** `RagDocumentEmbeddingServices/app/infrastructure/extractors/`.
10. **¿Justifica incorporación?:** Sí (P1 para nivel ligero MIT; P2 opcional para `Docling`).

### 2.3 Fragmentación semántica, indexación incremental, deduplicación y cola asíncrona
1. **Problema:** La ingesta síncrona bloquea el request HTTP al subir PDFs grandes o con OCR; subir el mismo archivo sin `Idempotency-Key` duplica documentos; actualizar metadatos o reindexar fuerza reprocesar todo.
2. **Valor:** Resiliencia ante archivos pesados, feedback de progreso real y ausencia de duplicados accidentales.
3. **Enfoques técnicos:** Cola liviana sobre PostgreSQL (`FOR UPDATE SKIP LOCKED` sobre `documents.status = 'PENDING'`, sin necesidad de añadir Redis/RabbitMQ) + worker ligero en `RagDocumentEmbeddingServices`; índice sobre `content_sha256` por tenant; chunking estructural que respete bloques de tablas Markdown y guarde `char_start`/`char_end` + `page` + `section`.
4. **Limitaciones:** Requiere polling/SSE de estado en UI (ya existe `GET /documents/{id}/status`).
5. **100 % local:** Sí.
6. **Dependencias:** PostgreSQL 16 (ya existente).
7. **Consumo de recursos:** Muy bajo (mismo proceso o worker ligero).
8. **¿Existe en el proyecto?:** Parcialmente (`process_document_worker.py` existe pero sin bucle/cola activa; chunking estructural ya guarda `page`/`section`).
9. **Reutilización:** `RagDocumentEmbeddingServices`.
10. **¿Justifica incorporación?:** Sí (P1).

---

## 3. Recuperación inteligente (RAG)

### 3.1 Reranking local, reescritura de consultas y filtrado enriquecido
1. **Problema:** La fusión RRF de HNSW + FTS mejora la cobertura, pero no evalúa la interacción fina pregunta-fragmento; las preguntas de seguimiento ("¿y cuál es la multa en ese contrato?") fallan en búsqueda sin reescritura; solo se puede filtrar por `document_ids` (máx. 12).
2. **Valor:** Mayor precisión en Top-5 (menos ruido enviado al LLM local pequeño) y conversaciones multi-turno naturales.
3. **Enfoques técnicos:**
   - **Reranker opcional local en CPU:** `BAAI/bge-reranker-v2-m3` (MIT, multilingüe) o variante cuantizada ONNX/INT8 activable por flag (`RERANKER_ENABLED`), aplicado sobre los Top-15 candidatos de RRF para entregar Top-5.
   - **Reescritura ligera de consultas:** Cuando existe historial de conversación, condensar la pregunta actual con el último turno del usuario usando el mismo proveedor LLM (o heurística determinista en modelos lentos).
   - **Filtros:** Permitir filtrar por `folder_id`, `collection_id`, `tags` y rango de fechas en `VectorRepositoryPgVector`.
4. **Limitaciones:** Un cross-encoder completo añade ~150–600 ms en CPU por consulta; la reescritura con LLM añade 1 llamada extra (costosa en Ollama CPU puro, debe ser opcional).
5. **100 % local:** Sí.
6. **Dependencias:** Opcional `onnxruntime` (MIT) + modelo reranker MIT; PostgreSQL para filtros.
7. **Consumo de recursos:** Reranker ONNX INT8: ~400–700 MB RAM; filtros SQL: despreciable.
8. **¿Existe en el proyecto?:** No encontrado (RRF existe; reranking, reescritura y filtros por carpeta/tag no).
9. **Reutilización:** `RagDocumentChatServices`.
10. **¿Justifica incorporación?:** Sí (P1 para filtros y umbral de evidencia; P2 para reranker opcional y reescritura).

### 3.2 Citas verificables, navegación exacta a evidencias e incertidumbre explícita
1. **Problema:** Aunque `page` y `section` se extraen en ingesta, se pierden antes del prompt LLM y de la respuesta HTTP; clicar `[Fuente N]` no abre el documento en la página ni resalta el fragmento; con 0 chunks relevantes el LLM igual responde.
2. **Valor:** Confianza auditable: el usuario verifica en 1 clic de dónde salió cada dato y recibe aviso honesto cuando no hay evidencia suficiente.
3. **Enfoques técnicos:** Exponer `page`, `section`, `chunk_index`, `char_start`, `char_end` en `ChatSourceResponse` y en `_format_context`; gate programático de evidencia insuficiente cuando `len(chunks) == 0` o `max_score < threshold`; visor PDF en frontend (PDF.js MIT o renderizado por página) con salto directo a `#page=N` y resaltado del texto citado.
4. **Limitaciones:** Resaltado exacto en PDFs escaneados depende de cajas delimitadoras OCR; en primera fase basta resaltar en texto/chunk y saltar a página en PDF.
5. **100 % local:** Sí.
6. **Dependencias:** Ninguna en backend; opcional `pdfjs-dist` (Apache-2.0) en frontend si se decide visor embebido sin depender del plugin del navegador.
7. **Consumo de recursos:** Bajo (~1–2 MB en bundle lazy del visor PDF).
8. **¿Existe en el proyecto?:** Parcialmente (`chunk_metadata` ya guarda `page`/`section`, `SafeMarkdown` ya renderiza `[Fuente N]` clicables).
9. **Reutilización:** `RagDocumentChatServices` + `DocumentPreviewModal.tsx` + `SourceList.tsx`.
10. **¿Justifica incorporación?:** Sí (P0/P1) — mayor diferenciador de confianza en RAG documental.

---

## 4. Investigación documental y generación de conocimiento

### 4.1 Informes estructurados, matrices de evidencia, grafos, líneas de tiempo y herramientas de estudio
1. **Problema:** Los usuarios no solo hacen preguntas sueltas; necesitan producir informes ejecutivos con citas verificadas, matrices comparativas, mapas conceptuales, líneas de tiempo, tarjetas de estudio (SM-2) y cuestionarios desde sus colecciones.
2. **Valor:** Convierte una biblioteca pasiva en un entorno de estudio, análisis e investigación verificable.
3. **Enfoques técnicos:** Completar `KnowledgeStudioServices` reparando el mapeo a `studio.artifact_versions`, conectando el cliente LLM multi-proveedor (`TenantLLMConfigResolver` compartido o cliente Ollama/Groq), activando el worker sobre `studio.studio_jobs`, y conectando `StudioPage.tsx` con `VerifiedVisualsPanel`, generadores reales de flashcards/quizzes y exportación MD/CSV/PDF.
4. **Limitaciones:** Informes extensos sobre muchos documentos en modelos locales 3B–8B requieren generación por secciones (map-reduce ligero) para no desbordar la ventana de contexto.
5. **100 % local:** Sí.
6. **Dependencias:** Ninguna externa nueva; reutiliza PostgreSQL (`studio.*`), Ollama/Groq y `DocumentExportServices`.
7. **Consumo de recursos:** Moderado (dependiente del modelo LLM local elegido).
8. **¿Existe en el proyecto?:** Implementado parcialmente (esquema SQL, dominio, validación de groundedness, SM-2 y `VerifiedVisualsPanel` existen, pero desconectados y sin LLM/worker).
9. **Reutilización:** **100 % sobre `KnowledgeStudioServices` y `StudioPage.tsx`** (no crear un módulo paralelo).
10. **¿Justifica incorporación?:** Sí (P0 para reparar esquema SQL y handoff; P1 para conectar LLM, worker y UI real).

---

## 5. Inteligencia documental proactiva

### 5.1 Extracción estructurada, vencimientos, obligaciones, hallazgos y acciones autorizadas
1. **Problema:** Contratos, pólizas, licencias y normativas contienen fechas de vencimiento, renovaciones automáticas, penalizaciones, montos y contradicciones que hoy solo se detectan si alguien pregunta manualmente o sobre snippets de 300 caracteres.
2. **Valor:** Anticipa riesgos operativos/legales y entrega hallazgos estructurados con procedencia por campo, separados estrictamente de cualquier acción externa o escritura (que requiere revisión humana).
3. **Enfoques técnicos:** Esquemas Pydantic versionados por tipo documental (`Obligation`, `Deadline`, `MonetaryTerm`, `RiskFinding`) con procedencia (`document_id`, `page`, `chunk_index`, `quote`), combinación de extractores deterministas (regex/fechas sobre documento completo) + extracción LLM estructurada (`json_schema` / structured outputs en Ollama/Groq), persistencia de hallazgos en tabla dedicada y cola de revisión humana que convierte hallazgos aprobados en asignaciones, notificaciones o artefactos de Studio.
4. **Limitaciones:** Modelos <7B presentan menor fidelidad en extracción JSON compleja; requiere validación Pydantic estricta y verificación determinista de fechas/montos.
5. **100 % local:** Sí.
6. **Dependencias:** Pydantic v2 (ya instalado), PostgreSQL 16.
7. **Consumo de recursos:** Bajo en extracción determinista; moderado en extracción LLM por documento.
8. **¿Existe en el proyecto?:** Parcialmente (`contract_comparator.py`, `expiration_detector.py`, `risk_assessor.py` y `extract_deterministic_facts` existen en `AgentOrchestratorServices`, pero sobre snippets truncados y sin persistencia de hallazgos).
9. **Reutilización:** Ampliar `AgentOrchestratorServices` + `DocumentAccessServices` (`notifications` y `document_assignments`).
10. **¿Justifica incorporación?:** Sí (P1/P2). Ver análisis detallado en [04_DOCUMENT_INTELLIGENCE_OPPORTUNITIES.md](./04_DOCUMENT_INTELLIGENCE_OPPORTUNITIES.md).

---

## 6. Agentes, automatizaciones y MCP

### 6.1 Orquestación confiable, checkpoints reales, streaming y compatibilidad con modelos pequeños
1. **Problema:** El orquestador actual corre síncronamente, tiene fallos de persistencia en PostgreSQL real, carece de herramienta RAG semántica y su `system_prompt` no enseña el formato de fallback JSON a modelos locales pequeños.
2. **Valor:** Permite tareas complejas multi-paso (comparar contratos, investigar corpus, agregar cifras en Code Mode) con trazabilidad, cancelación real y control humano.
3. **Enfoques técnicos:** Reparar persistencia (`agents.agent_runs`, `agent_approvals`, `AuditLogger`), ejecutar el grafo en background task/worker con SSE real, añadir herramienta de búsqueda híbrida semántica vía MCP, formalizar el prompt de fallback JSON para Ollama 3B–8B, y decidir explícitamente si mantener el motor ligero propio actualizando `ADR_AGENT_ORCHESTRATOR.md` (recomendado por simplicidad y cero bloat) o adoptar `langgraph` real.
4. **Limitaciones:** Modelos 2B–3B tienen tasa de error alta en tool-calling multi-paso; conviene recomendar ≥7B (`qwen2.5:7b` / `qwen3:8b`) para modo agente complejo.
5. **100 % local:** Sí.
6. **Dependencias:** Ninguna nueva obligatoria.
7. **Consumo de recursos:** Bajo en el servicio Python (`<=512 MB`); consumo principal en Ollama.
8. **¿Existe en el proyecto?:** Implementado parcialmente (36 tests en memoria, brechas reales en PostgreSQL e integración).
9. **Reutilización:** `AgentOrchestratorServices` + `CodeSandboxRunner` + servidor MCP de `KnowledgeStudioServices`.
10. **¿Justifica incorporación?:** Sí (P0 para reparaciones de contrato/DB/auth; P1 para SSE real, herramienta semántica y fallback Ollama).

---

## 7. Integraciones y conectores

### 7.1 Conectores locales (carpeta vigilada / importación masiva) y sincronización incremental
1. **Problema:** En entornos locales y pymes, la fuente principal de documentos suele ser una carpeta local/NAS o un repositorio Git/Markdown, y quienes usan Google Drive esperan detectar actualizaciones sin re-importar todo manualmente.
2. **Valor:** Mantiene la biblioteca sincronizada con mínimo esfuerzo manual, priorizando fuentes locales sin exigir nube.
3. **Enfoques técnicos:**
   - **Conector de carpeta local (local-first):** Script/tarea opcional que escanea un directorio montado en solo lectura, calcula SHA-256, ingesta nuevos/modificados y marca eliminados sin salir del host.
   - **Google Drive incremental (opcional):** Guardar `external_file_id` y `modified_time`/`md5Checksum` para re-importar solo cambios bajo demanda (sin webhooks públicos obligatorios).
   - **Webhooks salientes opcionales (P2/P3):** Notificar eventos (`document.processed`, `finding.detected`) con validación anti-SSRF.
4. **Limitaciones:** La sincronización de ACLs externas heterogéneas (p. ej. directorios corporativos) añade complejidad alta; mantener modelo de permisos internos del tenant reduce riesgos de fuga.
5. **100 % local:** Sí para carpetas locales/Markdown/Git; opcional para Google Drive.
6. **Dependencias:** Ninguna externa obligatoria.
7. **Consumo de recursos:** Bajo.
8. **¿Existe en el proyecto?:** Parcialmente (`import-batch` para Markdown/ZIP y `GoogleDriveImportServices` manual).
9. **Reutilización:** `RagDocumentEmbeddingServices` + `GoogleDriveImportServices`.
10. **¿Justifica incorporación?:** Sí (P2 para carpeta local sincronizada y detección de cambios por SHA-256; P3 para webhooks salientes; descartar búsqueda federada remota compleja).

---

## 8. Capacidades evaluadas y descartadas (o postergadas)

| Capacidad del ecosistema | Decisión | Justificación técnica |
|---|---|---|
| Base de datos vectorial separada (servicio externo adicional) | **DESCARTAR** | `pgvector` HNSW + FTS GIN en PostgreSQL 16 resuelve recuperación híbrida, transacciones ACID y permisos multiempresa sin sincronización distribuida ni más RAM. |
| Broker de colas externo (Redis/RabbitMQ/Celery) | **DESCARTAR** | Para despliegue local-first, PostgreSQL `FOR UPDATE SKIP LOCKED` ya cubre colas asíncronas (patrón ya usado en `document_deletions` y `studio_jobs`) con 0 contenedores extra. |
| Síntesis de audio tipo podcast largo por defecto | **POSTERGAR (P3)** | Alto consumo de CPU/VRAM y valor marginal frente a citas verificables, OCR en español y Studio operativo; solo viable como extensión opcional con Piper TTS. |
| Búsqueda federada en vivo contra APIs SaaS externas | **DESCARTAR** | Contradice la operación offline y complica la privacidad/latencia; preferir ingestión local controlada con permisos del tenant. |
| Reemplazo de `CodeSandboxRunner` por sandbox cloud | **DESCARTAR** | El sandbox local Deno `--deny-all` en red `internal: true` cumple el aislamiento sin exponer documentos fuera del equipo. |
| Librerías AGPL-3.0 (p. ej. `PyMuPDF4LLM`) en el núcleo MIT | **DESCARTAR** | Incompatibilidad de licenciamiento copyleft fuerte con la licencia MIT de Blandskron Documental. |
