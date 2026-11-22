# 05 — Investigación de Calidad del Pipeline RAG y Procesamiento Documental

- **Servicios auditados:** `RagDocumentEmbeddingServices`, `RagDocumentChatServices`, `DocumentSearchServices`, `DocumentAccessServices` y `scripts/eval/`.
- **Commit base:** `develop@5a4fac2` (22 de noviembre de 2026).

---

## 1. Diagnóstico factual del RAG actual

### 1.1 Lo que ya está bien diseñado
1. **Arquitectura unificada en PostgreSQL 16 + `pgvector`:** Evita sincronización distribuida con motores externos. Los permisos multiempresa (`tenant_id`, `owner_user_id`, `owner_groups`, `document_assignments`) se aplican **dentro de la misma consulta SQL** que la búsqueda vectorial y FTS (`VectorRepositoryPgVector._apply_access_filter`).
2. **Recuperación híbrida HNSW + FTS + RRF:** `scripts/database/migrations/008_hnsw_and_fts_indexes.sql` define índice HNSW (`m=16, ef_construction=64`, `vector_cosine_ops`), columna generada `content_tsv` (`to_tsvector('spanish', ...)`) con GIN e índice trigram GIN en `filename`. `VectorRepositoryPgVector.search_similar` fusiona hasta `max(limit*3, limit)` candidatos vectoriales y FTS con `RRF_K = 60`.
3. **Embeddings locales 100 % offline y verificados por SHA-256:** `intfloat/multilingual-e5-small` (384 dims, `device="cpu"`, `local_files_only=True`, `normalize_embeddings=True`) con prefijos correctos `"passage: "` en ingesta y `"query: "` en consulta.
4. **Chunking estructural base:** `CreateDocumentEmbeddings._split_structured` (`MAX_CHUNK_SIZE=1200`, `CHUNK_OVERLAP=160`) respeta saltos de `[page N]` y encabezados Markdown `#..######`, guardando `page` y `section` en `chunk_metadata`.
5. **Protección de historial:** `ChatHistoryRepositoryPg` solo inyecta mensajes `USER` previos (omite `ASSISTANT`), evitando filtrar respuestas basadas en documentos cuyo acceso fue revocado posteriormente.

### 1.2 Problemas reales comprobados que degradan la calidad RAG
1. **PDFs escaneados fallan y OCR no soporta español:** `PdfExtractor` (`pypdf`) no tiene fallback OCR; si `extract_text()` devuelve vacío lanza `ExtractionError`. Además, `RagDocumentEmbeddingServices/Dockerfile` solo instala `eng.traineddata`, degradando tildes y `ñ` en español incluso en imágenes PNG/JPEG/TIFF.
2. **Pérdida de estructura en tablas y ausencia de XLSX/PPTX:** `pypdf` aplana tablas a texto desordenado; `DocxExtractor` procesa todas las tablas después de todos los párrafos perdiendo su contexto; `PlainTextExtractor` ingiere CSV como texto crudo sin conservar encabezados por fila.
3. **Citas truncadas sin página ni sección:** Aunque `chunk_metadata` almacena `page` y `section`, `GroqLLMProvider._format_context` solo pasa `archivo`, `document_id`, `chunk_index` y `score`, y `ChatSourceResponse` solo devuelve `document_id`, `chunk_id`, `content`, `score` y `filename`.
4. **Sin gate de evidencia insuficiente:** `min_similarity_score` vale `0.0` por defecto. Aun cuando no se recupera ningún fragmento útil, el sistema invoca al LLM con `"No hay contexto documental relevante."`, dependiendo únicamente del prompt para evitar alucinaciones.
5. **Sin reescritura de consultas multi-turno:** El historial conversacional se pasa al LLM pero no a la etapa de retrieval; preguntas de seguimiento (*"¿y qué penalización aplica en ese caso?"*) recuperan fragmentos irrelevantes.
6. **Sin reranking:** RRF combina rankings sin evaluar semánticamente el par `(pregunta, fragmento)` en detalle; en corpora con documentos parecidos (p. ej. múltiples contratos), el ruido en Top-5 penaliza especialmente a modelos locales 3B–8B.
7. **Brecha de seguridad en delimitadores XML:** `RagDocumentChatServices` envuelve chunks en `<document_context>`, pero **no neutraliza** etiquetas `</document_context>` que un documento malicioso pueda contener.
8. **Score mixto tras RRF:** `fuse_reciprocal_rank` conserva el `score` crudo del primer origen (coseno `[0..1]` o `ts_rank_cd`), haciendo inconsistente cualquier umbral posterior.
9. **Pseudo-streaming SSE y contexto fijo:** `chat_routes.py` espera la respuesta entera del LLM y luego trocea cada 160 chars; en modo resumen (`MAX_CONTEXT_CHUNKS = 24 * 1200` chars ≈ 7.5K–9K tokens) puede saturar modelos Ollama de ventana pequeña (4K–8K).
10. **Evaluación actual no mide el RAG real:** `scripts/eval/run_eval_baseline.py` implementa un proxy léxico en Python puro que **nunca invoca `multilingual-e5-small`, HNSW, PostgreSQL FTS ni un LLM**.

---

## 2. Estrategia técnica de mejora escalonada (sin cambiar PostgreSQL ni `pgvector`)

### Fase A — Correcciones de alto impacto y bajo coste (P0/P1)
1. **OCR español + PDF escaneado:** Añadir `tesseract-ocr-spa` (`lang="spa+eng"`) y detectar páginas PDF con `< 40` caracteres de texto para rasterizarlas con `pypdfium2` (Apache-2.0) y pasarlas por Tesseract, guardando `metadata.ocr_applied = true` y confianza media.
2. **Parsing tabular MIT ligero:**
   - `pdfplumber` (MIT) para extraer tablas PDF a Markdown (`| col1 | col2 |`).
   - Recorrer párrafos y tablas en orden real del XML en `python-docx`.
   - `openpyxl` (MIT) para XLSX y `python-pptx` (MIT) para PPTX; CSV normalizado repitiendo encabezados por bloque.
   - Mantener los bloques de tabla intactos durante `_split_structured` para no partir filas a la mitad.
3. **Citas completas + evidencia insuficiente + anti-inyección:**
   - Exponer `page`, `section`, `chunk_index`, `char_start`, `char_end` y `rrf_score` en `_format_context` y `ChatSourceResponse`.
   - Escapar `</?document_context>` y tokens especiales en `RagDocumentChatServices` (reutilizando la misma función `neutralize_document_snippet` ya probada en `AgentOrchestratorServices`).
   - Implementar umbral configurable de evidencia insuficiente (`MIN_EVIDENCE_SCORE` + respuesta directa trazable si `len(chunks) == 0` sin malgastar inferencia LLM).
4. **Streaming SSE real y presupuesto de contexto adaptativo:** Consumir `stream=True` real del SDK `openai` (compatible con Ollama y Groq) y calcular `max_context_chunks` según la ventana del modelo configurado.
5. **FTS bilingüe/configurable:** Mantener `'spanish'` como diccionario principal y evaluar combinación con `'simple'` para códigos, SKUs, siglas y términos en inglés que el stemmer español no reduce bien.

### Fase B — Mejoras avanzadas opcionales (P2)
1. **Reranker local opcional (`RERANKER_ENABLED=false` por defecto):**
   - Aplicar `BAAI/bge-reranker-v2-m3` (MIT) cuantizado en ONNX INT8 sobre los Top-15 candidatos de RRF para entregar Top-5 al LLM.
   - Beneficio: +10–25 % típico en Precision@5 y NDCG@5 en corpora multilingües con documentos similares; activable solo en equipos con ≥8 GB RAM.
2. **Reescritura ligera de consultas multi-turno (`QUERY_REWRITE_ENABLED`):**
   - Activable solo cuando existe historial previo en la sesión; condensa la pregunta anafórica en una consulta autocontenida antes de llamar a `search_similar`.
3. **Filtros enriquecidos en retrieval:** Ampliar `ChatAskRequest` y `VectorRepositoryPgVector` para filtrar por `folder_id`, `collection_id`, `tags` y `date_range` además de `document_ids`.
4. **Decisión sobre embeddings (`intfloat/multilingual-e5-small` vs `BAAI/bge-m3`):**
   - **Recomendación actual: MANTENER `intfloat/multilingual-e5-small` (384d) por defecto.**
   - Justificación: Pesa ~471 MB, corre fluido en CPU incluso en equipos de 8 GB RAM, y cambiar a `BAAI/bge-m3` (1024d, ~2.2 GB) exigiría migración de columna `vector(384) -> vector(1024)`, reconstrucción completa de índices HNSW, reindexación de todos los documentos existentes y 4–5x más tiempo/RAM en CPU. Solo justificaría evaluarse como perfil opcional futuro si la evaluación real (Sección 3) demuestra una brecha insalvable en Recall@10 que el reranker no resuelva.

---

## 3. Metodología de evaluación reproducible (Etapa VIII)

Para dejar de operar a ciegas, se define una suite reproducible ejecutable en `ci-integration.yml` y localmente contra PostgreSQL 16 + `multilingual-e5-small` reales, ampliando `tests/fixtures/eval_corpus/`:

### 3.1 Corpus de evaluación sintético ampliado (sin datos personales)
- **S1–S5 actuales (Markdown):** Consultas simples, multi-documento, multi-salto, adversariales (prompt injection) y ruido.
- **S6 — Tablas y cifras (PDF/DOCX/XLSX/CSV sintéticos):** Balances, cronogramas y matrices de precios.
- **S7 — PDFs escaneados en español:** Imágenes con texto con tildes/ñ y tablas simples para medir CER/WER de OCR.
- **S8 — Preguntas sin respuesta en el corpus:** Consultas fuera de dominio para medir tasa de rechazo honesto (*abstention rate*).

### 3.2 Métricas obligatorias y umbrales objetivo

| Categoría | Métrica | Fórmula / Definición | Estado actual | Umbral objetivo (P1) |
|---|---|---|---|---|
| **Retrieval** | `Recall@5` / `Recall@10` | Fracción de documentos/chunks relevantes recuperados en Top-K real (HNSW+FTS+RRF) | **Pendiente de medir en real** (hoy solo proxy léxico) | ≥ 0.85 (`@5`), ≥ 0.93 (`@10`) |
| **Retrieval** | `Precision@5` | Fracción de Top-5 que son relevantes | Pendiente | ≥ 0.70 |
| **Retrieval** | `MRR` | Promedio de `1 / rank` del primer chunk relevante | Pendiente | ≥ 0.80 |
| **Retrieval** | `NDCG@5` | Ganancia acumulada descontada normalizada | Pendiente | ≥ 0.80 |
| **Generación** | `Exactitud de citas` | % de `[Fuente N]` cuyo texto respalda la afirmación y apunta al `document_id`/`page` correcto | Pendiente | ≥ 0.90 |
| **Generación** | `Fidelidad al contexto` | % de afirmaciones verificables contra `chunk_content` | Pendiente (gate de Studio es mock) | ≥ 0.90 |
| **Generación** | `Tasa sin respaldo (S8)` | % de respuestas en S8 que admiten explícitamente evidencia insuficiente | Pendiente | ≥ 0.95 |
| **Procesamiento** | `Calidad OCR (CER)` | Character Error Rate en S7 español | Pendiente | ≤ 0.05 en escaneos limpios |
| **Procesamiento** | `Exactitud de tablas` | % de celdas clave preservadas tras extracción en S6 | Pendiente | ≥ 0.90 |
| **Rendimiento** | `Latencia retrieval P50/P95` | Tiempo de embedding query + HNSW + FTS + RRF | Pendiente | P50 ≤ 150 ms, P95 ≤ 400 ms |

### 3.3 Procedimiento de ejecución (pendiente de implementación en fase posterior)
1. Levantar `postgres` + `rag-document-embedding-service` + `rag-document-chat-service` con `.env.example` en el proyecto sintético `bd-final-check`.
2. Ingerir los conjuntos `S1`–`S8` mediante `POST /api/v1/documents/upload` registrando tiempo de indexación, RAM pico y errores.
3. Ejecutar las consultas de `ground_truth.json` en dos modos: (a) solo retrieval contra PostgreSQL real para métricas deterministas (`Recall@K`, `Precision@K`, `MRR`, `NDCG@5`, latencia P50/P95) y (b) end-to-end contra proveedor local Ollama (`qwen2.5:3b` / `qwen2.5:7b`) para medir citas, fidelidad y tasa de rechazo en S8.
4. Persistir el resultado fechado en `.release-reports/RAG_REAL_EVAL.json` sin mezclar nunca resultados del proxy léxico con resultados del sistema real.
