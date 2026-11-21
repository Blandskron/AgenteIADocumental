# FEATURE_BENCHMARK — Knowledge Studio vs. conceptos de NotebookLM y OSS

> Estado: benchmark de planificación (2026-11-21). El alcance adoptado (P0 en Fase 4; P1 en Fase 5; descartes explícitos) se rastrea en [roadmap.md](../../../roadmap.md).

Referencia de evolución y seguimiento de implementación en [roadmap.md](../../../roadmap.md).

## 1. Posición oficial sobre NotebookLM

- Documentación oficial consultada: Google NotebookLM Help Center ("NotebookLM basics", "Audio Overviews", Gemini Apps Privacy Hub) y el artículo técnico Google Research "NotebookLM Audio Overviews" (ambos accesibles a 2026-11-21): https://support.google.com/notebooklm/ , https://research.google/blog/.
- Hechos relevantes verificados en la documentación pública:
  - NotebookLM es un servicio **proprietario de Google, sin API pública documentada** para terceros (a 2026-11-21 no existe endpoint oficial de auto-despliegue ni SDK soportado). Conclusión: **no puede ser dependencia técnica**, solo referencia conceptual.
  - Sus conceptos nucleares: *notebooks* (espacios con fuentes), respuestas **grounded con citas numeradas a fragmentos**, resúmenes/informes/guías de estudio generados desde las fuentes, *flashcards* y cuestionarios automáticos, **Audio Overviews** (podcast TTS de dos voces, multi-turno), mapas mentales/diagramas, y funciones "Deep Research" añadidas al ecosistema Gemini.
  - El diseño de audio/video usa modelos TTS propios de Google; **no exportables a una pila self-hosted con calidad equivalente sin coste de licencia/modelo**.
- Política de este plan: copiamos **problemas de usuario**, no interfaz, nombres, flujos propietarios ni assets. "Knowledge Studio" es denominación propia genérica; se evita cualquier marca de terceros en UI/código.

## 2. Panorama open source pertinente (referencia de viabilidad, no de dependencia)

| Proyecto | Qué aporta como evidencia | Estado/licencia (verificado 2026-11-21) | Relevancia |
|---|---|---|---|
| **Open WebUI** | Chat RAG self-hosted con documentos, modo offline; demuestra demanda de "studio" local | MIT, muy activo | Patrón de jobs locales + citas; no reutilizamos código |
| **RAGFlow** (InfiniFlow) | Plantillas de chunking por tipo de documento, motor de "deep document understanding", tablas de extracción | Apache-2.0, activo | Valida plantillas de ingesta/artefacto; pesado (requiere Elasticsearch/Infinity) → incompatible con nuestro modo base simple |
| **Danswer / Onyx** | Conectores multi-fuente con permisos espejo | MIT/Comercial | Referencia para "Fuentes y conectores" (Fase 3), no para artefactos |
| **Quivr** | "Cerebro" personal con colecciones | Licencia cambiante (verificar en cada release) | Señal de producto, no de arquitectura |
| **txtai** | Embeddings + grafos relacionales embebidos en un proceso Python | Apache-2.0 | Referencia futura para grafos embebidos, no necesario para Studio P0 |
| **Mermaid + remark/rehype** | Render de diagramas/Markdown en cliente con sanitización | MIT | Base propuesta para visualización sin IA de imágenes |
| **reactflow (XYFlow)**, **Recharts**, **D3** | Mapas interactivos, gráficos numéricos | MIT | Render propio determinista desde datos estructurados |
| **python-pptx**, **openpyxl**, **reportlab** | Export PPTX/XLSX/PDF server-side sin red | MIT/MIT/BSD-3 (reportlab también comercial) | reportlab **ya está** en DocumentExportServices → reutilizable |
| **Coqui TTS / Piper / Kokoro** | TTS local de calidad razonable | MPL-2.0 / MIT / Apache-2.0 respectivamente (verificar voz/licencia por modelo) | Única vía coherente con "sin servicios externos obligatorios" para audio (P2) |

Ninguna de estas dependencias se adopta en esta fase; se listan para acotar costes y licencias si se implementan los módulos propuestos.

## 3. Qué ofrece ya Blandskron y qué NO debe duplicarse

Evidencia de código (rutas reales):

| Capacidad existente | Ruta | Implicación para Studio |
|---|---|---|
| Chat RAG con citas `[Fuente N] archivo/document_id/chunk_index/score` | `backend/RagDocumentChatServices/app/infrastructure/ai/llm_provider_groq.py` (`_format_context`, líneas ~102-110) | Studio **reutiliza el contrato de contexto citable**; no crea un segundo sistema de citas |
| Historial persistente conversaciones/mensajes/fuentes | `backend/ConversationServices/app/infrastructure/database/models.py` (`ConversationModel`, `ConversationMessageModel`, `ConversationDocumentModel`) | "Generar artefacto desde conversación" = nuevo `source_type` sobre estos ids, no tabla paralela |
| Búsqueda vectorial pgvector con filtro de acceso | `backend/DocumentSearchServices/app/application/documents/use_cases/search_documents.py`, `build_chat_context.py` | Selección de fuentes para artefactos pasa por el mismo control de acceso |
| Biblioteca con carpetas/permisos empresa-área | `backend/DocumentLibraryServices/app/application/use_cases/manage_library.py` | Las "colecciones" de Studio **no duplican originales**: referencias id+versión |
| Export PDF atómico con sha256, caducidad, capacidad e idempotencia | `backend/DocumentExportServices/app/application/use_cases/manage_exports.py` (`create_chat_pdf_export`, `download`, `export_status`) | Contrato excelente para **copiar el patrón**, pero hoy está acoplado a `source_type="chat_message"` y renderer único `ChatPdfRenderer`; ver ADR §4 |
| Ingesta con extracción de contenido y chunks | `backend/RagDocumentEmbeddingServices/app/application/documents/use_cases/upload_document.py`, `extract_document_content.py` | Fuentes de Studio = documentos ya ingeridos; Markdown/ZIP entra en Fase 3 (`R3-01`–`R3-04`) |
| Importación Drive con credenciales cifradas (TokenCipher) | `backend/GoogleDriveImportServices/app/infrastructure/google/token_cipher.py` | Reutilizado por configuración Groq (Fase 1, `R1-02`); Studio no gestiona secretos propios |
| Frontend Feature-Sliced (`entities/features/pages/shared/widgets`) | `frontend/src/*` | Studio es un *feature slice* + páginas nuevas, no una app aparte |

Brechas detectadas (necesarias para Studio y hoy inexistentes):
- **No hay framework de jobs asíncronos**: todo es request/response síncrono por servicio FastAPI; los PDFs se generan inline con worker aislado (`app/infrastructure/pdf/worker.py`). Artefactos LLM de minutos (informes largos, quizzes) exigen trabajos cancelables → decisión de arquitectura en ADR (cola ligera en PostgreSQL, no Celery/Redis aún).
- **No hay almacenamiento de artefactos versionados** (solo exports binarios inmutables).
- **No hay generación JSON estructurada validada** (el chat devuelve texto libre).

## 4. Matriz valor × complejidad (conceptos de NotebookLM aplicados a nuestro stack)

Valor percibido (V) y complejidad técnica (C) en escala 1-5, coste marginal ≈ tokens Groq + ingeniería.

| Concepto | V | C | Dep. externa | Nota |
|---|---|---|---|---|
| Consultas con citas | 5 | – | Ninguna | **Ya existe** (chat RAG). No duplicar |
| Espacios/colecciones temáticas | 4 | 2 | Ninguna | Capa lógica sobre documentos existentes |
| Resúmenes (ejecutivo/secciones/comparativo) | 5 | 2 | Groq opcional-funcional | P0 natural: mismo provider del chat |
| Informes/guías/glosarios/FAQ/minutas | 4 | 2 | Ninguna extra | Plantillas prompt+schema JSON |
| Tabla de evidencia/comparación + CSV | 4 | 2 | Ninguna extra | Extracción con validación pydantic; export CSV trivial |
| Tareas propuestas con revisión humana | 4 | 3 | Ninguna (MCP opcional) | Nunca auto-ejecución (principio 3) |
| Flashcards/quizzes | 4 | 2 | Ninguna extra | Reutiliza plantilla+cita; almacenamiento local |
| Mapas mentales/conceptuales | 3 | 3 | Ninguna extra | Datos estructurados + reactflow/Mermaid, export SVG |
| Cronologías/diagramas/charts | 3 | 3 | Ninguna extra | Solo desde cifras verificadas con procedencia |
| Diapositivas PPTX/PDF | 3 | 4 | python-pptx | Edición previa obligatoria anti-alucinación |
| Audio resumen (TTS) | 3 | 5 | Local (Piper/Kokoro) u opt. proveedor | P2; degradación honesta si no hay motor |
| Video-resumen / infografías ricas | 2 | 5 | Multimedia pesada | **Descartado por defecto** |
| Deep research multi-paso | 3 | 5 | Presupuesto LLM alto | P2 experimental, alcance cerrado a fuentes propias |

## 5. Diferencias asumidas frente a NotebookLM (sin prometer paridad)

1. Sin Audio Overview dual-voz conversacional de calidad Google: ofrecemos guion citado + TTS mono local opcional (P2), honestamente inferior.
2. Sin generación de imágenes ni "infographics" neuronales: solo diagramas deterministas desde datos.
3. Sin búsqueda web ni "Discover": el corpus es lo que el usuario autoriza (coherente con modo base offline salvo LLM).
4. Sin sharing público por enlace: compartir respeta empresa/área/usuario (principio 5).
5. A cambio: **self-hosted, multiempresa, datos nunca salen del perímetro salvo inferencia LLM elegida, artefactos editables y auditables**.

## 6. Referencias consultadas (2026-11-21)

- NotebookLM Help Center — support.google.com/notebooklm (capacidades y límites de producto; ausencia de API pública).
- Google Research blog — "NotebookLM: AI-powered thinking partner" / "Audio Overviews" (diseño conceptual de audio multi-voz).
- github.com/open-webui/open-webui (MIT) · github.com/infiniflow/ragflow (Apache-2.0) · github.com/onyx-dot-app/onyx (MIT) · github.com/QuivrHQ/quivr · github.com/neuml/txtai (Apache-2.0).
- mermaid.js.org (MIT, directiva `securityLevel`) · xyflow.net/react-flow (MIT) · recharts.org (MIT) · python-pptx (MIT) · openpyxl (MIT) · reportlab (BSD-3 con opciones comerciales) · rhasspy/piper (GPL-3 código, voces varias licencias) · hexgrad/kokoro (Apache-2.0 pesos a verificar por versión) · coqui-ai/TTS (Mozilla Public 2.0 tras fork).
- Docs internas del repo: `README.md`, `AGENTS.md`, `docs/architecture.md`, `backend/README.md`, `frontend/AGENTS.md`.
