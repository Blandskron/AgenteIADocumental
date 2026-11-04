# RagDocumentEmbeddingServices

Lee el [contrato del servicio](README.md) y toma la tarjeta activa del [tablero](../../ROADMAP.md#ragdocumentembeddingservices).

- Revisa el cliente del frontend y GoogleDriveImportServices cuando cambies el contrato de carga.
- Mantén los embeddings compatibles con el modelo, la normalización y las 384 dimensiones del servicio de chat. Usa el prefijo de pasaje para indexar.
- Prueba carga, extracción y reindexación con documentos sintéticos y almacenamiento aislado. Valida Compose desde la raíz y los cambios de persistencia con PostgreSQL y pgvector.
