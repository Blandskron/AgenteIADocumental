# 06 — Investigación de Modelos de IA Gratuitos y Operación Local

- **Objetivo:** Evaluar modelos y motores open source gratuitos ejecutables localmente (100 % offline tras descarga inicial) por categoría funcional y perfil de hardware real (**4 GB, 8 GB, 16 GB y 32 GB de RAM**).
- **Principio de honestidad:** Ningún modelo se recomienda por encima de la capacidad real del hardware. Si un equipo de 4 GB RAM no puede ejecutar confortablemente el stack Docker completo + un LLM, se declara explícitamente.

---

## 1. Situación actual en Blandskron Documental

- **Embeddings actuales:** `intfloat/multilingual-e5-small` (licencia MIT, 384 dims, ~471 MB, `sentence-transformers` + `torch` CPU, `local_files_only=True`).
- **Motor LLM local actual:** Ollama (`docker/compose/ollama.yml`, perfil `--profile local-llm`, puerto `127.0.0.1:11434`). Allowlist actual en `AuthServices/users/ollama_integrations.py`: `gemma2:2b`, `qwen2.5:3b`, `llama3.2:3b`, `phi3:mini`, `mistral:7b`.
- **OCR actual:** Tesseract 5.5.4 (Apache-2.0) en `RagDocumentEmbeddingServices` — actualmente solo con `eng.traineddata` (falta `spa.traineddata`).
- **Proveedores externos opcionales:** Groq (API key cifrada en `tenant_integrations`) y `openai_compatible` (implementado en fábrica LLM, pendiente de exponer en `GroqConfigResolver` y UI).

---

## 2. Evaluación comparativa de modelos y motores locales por categoría

### 2.1 Modelos generativos locales (vía Ollama / `llama.cpp`, cuantización `Q4_K_M`)

| Modelo | Licencia | Español / Multilingüe | Tamaño disco (`Q4_K_M`) | RAM requerida (modelo + KV) | Contexto útil local | Tool calling / JSON | Compatibilidad Ollama | Recomendación |
|---|---|---|---|---|---|---|---|---|
| **Qwen 2.5 1.5B** (`qwen2.5:1.5b`) | Apache 2.0 | Bueno para su tamaño | ~1.0 GB | ~1.8–2.2 GB | 4K–8K | Básico (JSON simple) | Total | Chat RAG mínimo en equipos ajustados (no recomendado para agentes complejos). |
| **Qwen 2.5 3B** (`qwen2.5:3b`) | Apache 2.0 | Muy bueno | ~1.9 GB | ~3.0–3.5 GB | 8K–16K | Aceptable (con guía) | Total (ya en allowlist) | **Mejor equilibrio en 8 GB RAM** para chat RAG y resúmenes en español. |
| **Phi-4-mini (3.8B)** (`phi4-mini`) | MIT | Bueno | ~2.5 GB | ~3.5–4.0 GB | 8K–16K | Bueno en razonamiento | Total | Alternativa MIT sólida en 8 GB RAM para extracción y lógica. |
| **Llama 3.2 3B** (`llama3.2:3b`) | Llama Community License* | Bueno (tiende a anglicismos) | ~2.0 GB | ~3.0–3.5 GB | 8K–16K | Aceptable | Total (default actual) | Válido; inferior a Qwen en español técnico. |
| **Qwen 3 8B / Qwen 2.5 7B** (`qwen3:8b`, `qwen2.5:7b`) | Apache 2.0 | **Excelente** (referencia en español) | ~4.7–5.2 GB | ~6.5–8.0 GB | 16K–32K | **Muy bueno** (nativo) | Total | **Recomendado para 16 GB RAM** (RAG + Studio + Agentes + extracción estructurada). |
| **Mistral Nemo / Small (12B)** (`mistral-nemo`, `mistral-small`) | Apache 2.0 | **Excelente** (lenguas europeas) | ~7.1–14 GB | ~9.5–16 GB | 32K | Muy bueno | Total | Ideal en 16–32 GB RAM para informes extensos y comparación contractual. |
| **Gemma 3 (4B / 12B)** (`gemma3:4b`, `gemma3:12b`) | Gemma Terms of Use* | Muy bueno | ~3.3 / 8.1 GB | ~4.5 / 10.5 GB | 16K–32K | Bueno + **visión** | Total | Útil si se requiere comprensión visual de páginas/diagramas en local. |
| **DeepSeek-R1-Distill 14B** (`deepseek-r1:14b`) | MIT | Muy bueno | ~9.0 GB | ~11.5–13 GB | 16K–32K | Razonamiento profundo | Total | Perfil 32 GB RAM (o 16 GB con GPU) para análisis legal/técnico complejo. |

> *Nota sobre licencias y redistribución:* Los modelos con licencia **Apache 2.0** (`Qwen 2.5`, `Qwen 3`, `Mistral`) y **MIT** (`Phi-4-mini`, `DeepSeek-R1-Distill`) no imponen restricciones de redistribución ni umbrales de usuarios. `Llama Community License` y `Gemma Terms of Use` son gratuitos para uso local/comercial estándar, pero tienen cláusulas específicas de uso aceptable/atribución; por ello el software nunca embebe pesos generativos y permite al usuario descargar el modelo que elija vía Ollama.

### 2.2 Embeddings locales

| Modelo | Licencia | Dims | Español | Tamaño | RAM CPU | Estado / Decisión |
|---|---|---|---|---|---|---|
| **`intfloat/multilingual-e5-small`** | MIT | 384 | Muy bueno | ~471 MB | ~600 MB | **MANTENER COMO ESTÁNDAR.** Excelente relación calidad/velocidad/RAM en CPU y ya empaquetado con verificación SHA-256. |
| `BAAI/bge-m3` | MIT | 1024 | Excelente (denso + léxico) | ~2.2 GB | ~2.8 GB | **NO CAMBIAR AHORA.** Exigiría migración `vector(384)->vector(1024)`, reindexación total y 4–5x más coste en CPU. Evaluar solo si `eval` real demuestra necesidad. |
| `nomic-embed-text-v2-moe` | Apache 2.0 | 768 | Muy bueno | ~1.0 GB | ~1.5 GB | Alternativa futura si se soporta multi-modelo; hoy innecesario. |

### 2.3 Reranking local (Cross-Encoder opcional)

| Modelo / Motor | Licencia | Español | Tamaño | RAM CPU | Latencia (15 chunks CPU) | Decisión |
|---|---|---|---|---|---|---|
| **`BAAI/bge-reranker-v2-m3` (ONNX INT8)** | MIT | Excelente | ~570 MB (INT8) | ~650 MB | ~200–500 ms | **OPCIONAL (P2)** detrás de `RERANKER_ENABLED=false` para equipos ≥8–16 GB RAM. |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Apache 2.0 | Bajo (entrenado en inglés) | ~90 MB | ~180 MB | ~40–100 ms | Descartado como default por debilidad en español. |

### 2.4 OCR, layout de tablas y visión local

| Tecnología | Licencia | Español | Consumo RAM | CPU-friendly | Decisión |
|---|---|---|---|---|---|
| **Tesseract 5.5.4 + `spa.traineddata` + `pypdfium2`** | Apache 2.0 | Bueno en escaneos limpios | +200–500 MB pico | **Sí (rápido)** | **P0 — Incorporar de inmediato** en `RagDocumentEmbeddingServices`. |
| **`pdfplumber` + `openpyxl` + `python-pptx`** | MIT | N/A (estructural) | <150 MB | **Sí (muy rápido)** | **P1 — Incorporar** para tablas PDF y formatos ofimáticos. |
| **PaddleOCR / PP-Structure** | Apache 2.0 | Excelente (escaneos difíciles y tablas) | ~1.0–1.5 GB | Moderado (ONNX/CPU) | **P2 opcional** para equipos con alta carga de escaneos complejos. |
| **Docling (IBM Research)** | MIT | Excelente (layout + TableFormer) | ~1.5–2.5 GB | Moderado | **P3 opcional** (`--profile advanced-ingest`) para ≥16 GB RAM. |
| **PyMuPDF / PyMuPDF4LLM** | **GNU AGPL-3.0** | — | — | — | **DESCARTADO** por incompatibilidad copyleft con licencia MIT del proyecto. |
| **Gemma 3 / Qwen2.5-VL (vía Ollama)** | Gemma / Apache 2.0 | Muy bueno | ~4.5–9 GB | Lento en CPU (ideal GPU) | **P3 opcional** para descripción de gráficos/planos escaneados. |

### 2.5 Extracción estructurada, clasificación y voz (opcionales)
- **Extracción estructurada y clasificación:** No requieren un motor separado; usar **Capa 1 determinista** (regex/reglas en Python, 0 MB extra) + **Capa 2 LLM local** (`qwen2.5:7b` / `phi4-mini` con salida JSON validada por Pydantic v2).
- **Reconocimiento de voz (STT opcional — P3):** `faster-whisper` (MIT, basado en CTranslate2; modelos `small` ~500 MB / `medium` ~1.5 GB, excelente español offline en CPU).
- **Síntesis de voz (TTS opcional — P3):** `Piper` (MIT, voces ONNX en español <100 MB, tiempo real en CPU). Solo para accesibilidad o resúmenes hablados opcionales.

---

## 3. Matriz honesta de viabilidad por perfil de hardware (RAM)

El stack Docker core actual (PostgreSQL 16 + Auth + 9 servicios Python + Nginx + `multilingual-e5-small` cargado en Chat e Ingesta) consume aproximadamente **2.2–3.2 GB de RAM** en operación base.

| Perfil de equipo | Stack viable | Modelo LLM local realista | Capacidades operativas | Limitaciones honestas |
|---|---|---|---|---|
| **4 GB RAM** | **Insuficiente para stack completo + LLM local.** Solo viable como servidor ligero de búsqueda/biblioteca (sin LLM local) o con proveedor externo opcional (Groq) y reduciendo workers/duplicación E5. | Ninguno cómodo junto a 12 contenedores Docker (un modelo 1.5B + stack core provoca swap severo / OOM). | Registro, biblioteca, búsqueda FTS/vectorial ligera, preview/exportación; chat solo con proveedor externo opcional o consolidando servicios. | **No prometer Ollama local en 4 GB RAM con 12 contenedores.** Requiere modo ligero o proveedor externo opcional. |
| **8 GB RAM** | **Core completo + Ollama (`--profile local-llm`)** (evitar activar Studio + Agents + Code Mode simultáneamente si no hay swap/GPU). | `qwen2.5:3b` (`Q4_K_M`, ~1.9 GB) o `phi4-mini` (`3.8B`, ~2.5 GB). | Chat RAG fluido en español, OCR español, tablas ligeras, resúmenes y preguntas sobre 1–5 documentos. | Latencia en CPU pura: ~6–15 tokens/s; modo agente multi-paso con 3B puede requerir reintentos; sin reranker pesado ni `Docling`. |
| **16 GB RAM** | **Core + Ollama + Knowledge Studio + AgentOrchestrator + CodeSandboxRunner** en paralelo. | `qwen3:8b` / `qwen2.5:7b` (`Q4_K_M`, ~5 GB) o `gemma3:12b` (con GPU/Apple Silicon). | **Experiencia completa 100 % offline:** RAG con reranker opcional, Studio con informes/flashcards, Agentes con tool-calling fiable, Code Mode y extracción estructurada. | En CPU pura sin GPU, un 7B/8B corre a ~3–8 tokens/s (aceptable con SSE streaming real, lento sin streaming). Con GPU de 6–8 GB VRAM: >35 tokens/s. |
| **32 GB RAM** | **Todo el stack + extensiones opcionales** (reranker ONNX, `Docling`, Whisper/Piper). | `mistral-small` (12B–24B) o `deepseek-r1:14b` (`Q4_K_M`, ~9 GB). | Análisis contractual extenso, múltiples colecciones simultáneas, OCR/layout avanzado y razonamiento profundo 100 % local. | Consumo de disco estimado: 15–25 GB entre imágenes Docker, pesos E5 y modelos Ollama. |

---

## 4. Recomendaciones inmediatas para `AuthServices` (allowlist Ollama)

1. Actualizar la allowlist curada de `ollama_integrations.py` para incluir `qwen2.5:1.5b`, `qwen2.5:3b`, `phi4-mini`, `qwen2.5:7b`, `qwen3:8b` y `mistral-nemo`, etiquetando cada modelo en `SettingsAIPage.tsx` con su **requisito real de RAM** y **uso recomendado** (Chat rápido vs Agentes/Studio).
2. Evaluar a futuro (P2) evitar cargar dos copias independientes en RAM de `intfloat/multilingual-e5-small` (una en `RagDocumentEmbeddingServices` y otra en `RagDocumentChatServices`, ~600 MB cada una) para reducir ~600 MB del consumo base en equipos de 8 GB RAM.
