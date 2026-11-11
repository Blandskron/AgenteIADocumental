---
name: documental-ingest
description: "Mantener RagDocumentEmbeddingServices al cambiar su API, persistencia o integración. Recibe archivos, conserva el original y genera fragmentos y embeddings locales para su recuperación."
---

# documental-ingest

Lee las [instrucciones del ámbito](../../../backend/RagDocumentEmbeddingServices/AGENTS.md) y abre desde el [README](../../../backend/RagDocumentEmbeddingServices/README.md) la guía del contrato o de operación relevante.

1. Revisa la carga desde web y Drive al cambiar multipart, respuestas o estados.
2. Conserva E5, el prefijo de pasaje y las 384 dimensiones que espera Chat.
3. Valida carga, OCR y reindexación con originales sintéticos, almacenamiento aislado y PostgreSQL.
