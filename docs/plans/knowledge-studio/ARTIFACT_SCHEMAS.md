# ARTIFACT_SCHEMAS — formatos de datos de Knowledge Studio

Esquemas lógicos (se materializarían con pydantic v2 + JSON Schema versionado). 2026-11-21. Solo diseño; sin migraciones aplicadas. Convención: todos los ids son UUIDv7; todo artefacto pertenece a `(tenant_id, owner_id, visibility{private|area|company}, area_id?)`.

## 0. Envelope común `ArtifactContent`

```jsonc
{
  "schema_version": 1,
  "kind": "summary | report | evidence_table | tasks | quiz | flashcards | mindmap | timeline | chart | slides | audio_script",
  "language": "es",
  "body_md": "Markdown con marcadores [n] que referencian citations[].n",
  "citations": [ /* ver §1 */ ],
  "inferences": [ {"span": "…texto…", "reason": "síntesis entre fuentes", "confidence": "low|medium"} ],
  "gaps": ["No hay información sobre plazos en las fuentes seleccionadas"],
  "provenance": { /* ver §2 */ }
}
```

Reglas transversales:
- Todo enunciado factual debe resolver a un `citations[].n` o estar listado en `inferences[]`; el validador del job lo exige (política de citación por plantilla: `strict | labeled | none` — `none` solo permitido en mapas mentales jerárquicos y guiones derivados de artefactos ya citados).
- Ningún schema permite campos libres HTML/JS; SVG/Mermaid se guardan como **código fuente**, nunca como markup ejecutable.

## 1. `Citation`

```jsonc
{
  "n": 3,
  "document_id": "uuid",
  "document_version_sha": "sha256 del contenido ingerido",
  "chunk_index": 17,
  "page": 4,                    // opcional si el extractor lo provee
  "quote_span": {"start": 812, "end": 903},   // offsets en texto normalizado del chunk
  "quote_text": "fragmento literal citado",
  "score": 0.81,                 // similitud de recuperación (no de verdad)
  "status": "anchored | detached | stale"      // detached = edición humana rompió anclaje
}
```
Anclaje: `quote_text` debe coincidir (normalizando whitespace/puntuación) con `chunks[chunk_index][span]`. Si el documento se reindexa y el sha cambia → `stale`.

## 2. `Provenance` (por artefacto)

```jsonc
{
  "job_id": "uuid", "template_id": "report.risk_analysis", "template_version": 3,
  "model": "groq:<model-id>", "options_hash": "sha256", "created_at": "…",
  "source_fingerprint": "sha256(sorted(doc_id@sha))",
  "generated_by": "user|regeneration|mcp",       // mcp solo drafts de lectura
  "human_edited": false, "edited_versions": []
}
```

## 3. Esquemas específicos

### 3.1 Resumen (`kind=summary`)
```jsonc
{ "mode": "executive|sectioned|comparative",
  "sections": [{"title": "…", "body_md": "…", "source_docs": ["uuid"]}],
  "per_document": [{"document_id": "uuid", "title": "…", "version": "…", "summarized_at": "…"}],
  "key_findings": [{"text": "…", "citations": [1,4]}] }
```

### 3.2 Reporte plantillado (`kind=report`)
`report_type ∈ {technical, exec_memo, study_guide, glossary, faq, minutes, risk_analysis}`; cuerpo = `sections[]` con `heading`, `body_md`, `citations`; glosario añade `terms[{term, definition, citations}]`; FAQ añade `qa[{q,a,citations}]`; minuta añade `attendees[]` y `decisions[{text,citations}]`; riesgos añade `risks[{risk, likelihood, impact, mitigation, citations}]` (enums cerrados para likelihood/impact).

### 3.3 Tabla de evidencia (`kind=evidence_table`)
```jsonc
{ "columns": [{"id":"metric","label":"Métrica","type":"string|number|date|bool","unit_hint":"€|mes|…"}],
  "rows": [{"cells": {"revenue": {"value": 12.5, "display": "12,5 M€",
             "citations": [2]}, "as_of": {"value": "2025-03-31", "citations": [2]}}}],
  "filters_saved": null,
  "export_formats": ["csv","xlsx?P2","md"] }
```
Invariantes: celda numérica SIN cita ⇒ se marca `unverified: true` y el gráfico derivado la excluye por defecto. CSV export incluye columna oculta de procedencia (`doc_id#chunk`) activable por opción.

### 3.4 Tareas propuestas (`kind=tasks`)
```jsonc
{ "items": [{"title":"Solicitar anexo 3","due":"2026-12-01?",
    "assignee": {"name":"Ana","basis":"explicit|inferred"},
    "status":"proposed|accepted|rejected|done",
    "citations":[5], "external_action": null } ] }
```
`external_action` solo puede rellenarse tras confirmación humana explícita vía MCP (PROMPT 3) y guarda `{system, tool, payload_hash, confirmed_by, confirmed_at, result_status}` — nunca credenciales ni payloads sensibles completos.

### 3.5 Quiz (`kind=quiz`)
```jsonc
{ "questions": [{"id":"q1","difficulty":"easy|medium|hard","stem":"…","citations":[1],
    "type":"single_choice|true_false|short_answer",
    "options":[{"id":"a","text":"…","correct":true,"explanation":"…","explanation_citations":[1]}],
    "validation":{"unique_correct":true,"distractors_from_sources":true} }],
  "scoring": {"pass_threshold": 0.7}, "attempts_local": true }
```
El generador rechaza quizzes con >1 correcta o con explicación sin cita (fallback: pregunta descartada, no aprobada con warning silencioso).

### 3.6 Flashcards (`kind=flashcards`)
`cards[{front, back, citations, tags[], spaced_repetition:{ease, interval_days, due}}]` — SM-2 simplificado local, sin telemetría.

### 3.7 Mapa mental/conceptual (`kind=mindmap`)
```jsonc
{ "layout": "tree|graph",
  "nodes": [{"id":"n1","label":"Cláusula 5","type":"concept|entity|document|section","document_ref":"uuid?","citation_n":2?"}],
  "edges": [{"from":"n1","to":"n2","relation":"contains|references|precondition",
             "origin":"explicit_link|extracted|human",           // extracted ⇒ confianza requerida
             "confidence": 0.0-1.0?, "citations":[7]?}] }
```
Distinguir de GraphRAG (PROMPT 1): este grafo es **de presentación/negocio del artefacto**; si existiera grafo canónico, los nodos `entity` guardarían `graph_node_id` para no duplicar identidades. Export: JSON canónico + SVG/PNG render-client.

### 3.8 Cronología / diagrama / gráfico
- `timeline`: `events[{date|date_range, label, precision:"exact|month|year|approx", citations[]}]` — fechas no ancladas se marcan `approx`.
- `diagram`: `{"dialect":"mermaid","source":"graph TD; …"}` (sanitizado, ≤N líneas).
- `chart`: `{"chart_type":"bar|line|pie|scatter","dataset_ref":{"artifact_id":tableId,"column_map":{...}},"series":[{"label","cell_refs":[…]}],"units":"…"}` — **solo referencia tablas existentes; prohibido contener valores propios** (garantiza "gráficos no inventan números").

### 3.9 Diapositivas (`kind=slides`)
`slides[{layout:"title|bullets|table_ref|image_slot", title, bullets[{text,citations}], speaker_notes, table_cell_refs?[], status:"draft|reviewed"}]` — export PPTX requiere que todas sean `reviewed` o advertencia modal; `image_slot` admite solo figuras derivadas de `chart`/`mindmap`, nunca imágenes generadas.

### 3.10 Guion de audio (`kind=audio_script`, P2)
`segments[{speaker:"host", text, citations[], duration_estimate_s}]` + `tts:{engine:"piper|kokoro|provider_x", voice, voice_license}`; el binario resultante vive como export inmutable, no embebido en el artefacto.

## 4. Estado de job `StudioJob`

```jsonc
{ "job_id":"uuid","tenant_id":"uuid","user_id":"uuid",
  "op_key":"client idempotency","request_sha256":"…",
  "type":"generate|regenerate|export",
  "state":"PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED",
  "step":"retrieving|drafting|citing|validating|rendering",
  "progress": 0-100, "attempt": 1, "max_attempts": 3,
  "cancel_requested": false, "heartbeat_at":"…",
  "budget":{"max_input_tokens":…, "max_output_tokens":…, "spent_tokens":…},
  "error":{"code":"LLM_UNCONFIGURED|SCHEMA_INVALID|BUDGET_EXCEEDED|ACCESS_REVOKED|TIMEOUT","message_legible":"…"},
  "result_artifact_id":"uuid?", "cache_hit": false,
  "timing":{"queued_ms":…,"run_ms":…},"created_at":"…","finished_at":"…" }
```

API externa mínima (coherente con estilo de los servicios actuales):
`POST /studio/jobs` (202 + op_key), `GET /studio/jobs/{id}`, `POST /studio/jobs/{id}/cancel`,
`GET/PUT /studio/artifacts/{id}` (+`/versions`), `POST /studio/artifacts/{id}/exports`,
`GET /studio/collections` CRUD. Errores RFC7807-style como en el resto de servicios; jamás contenido de clave ni stack en mensajes.
