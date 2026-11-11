# RagDocumentEmbeddingServices

Skill del componente: [documental-ingest](../../.agents/skills/documental-ingest/SKILL.md).

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- Revisa el cliente del frontend y GoogleDriveImportServices cuando cambies el contrato de carga.
- Mantén los embeddings compatibles con el modelo, la normalización y las 384 dimensiones del servicio de chat. Usa el prefijo de pasaje para indexar.
- Prueba carga, extracción y reindexación con documentos sintéticos y almacenamiento aislado. Valida Compose desde la raíz y los cambios de persistencia con PostgreSQL y pgvector.
