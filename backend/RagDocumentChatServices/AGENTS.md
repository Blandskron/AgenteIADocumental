# RagDocumentChatServices

Skill del componente: [documental-rag](../../.agents/skills/documental-rag/SKILL.md).

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- Aplica los permisos documentales antes de recuperar fragmentos o construir el contexto enviado a Groq. Revisa tanto las preguntas como los resúmenes y el historial.
- Mantén la compatibilidad con el cliente de chat y con el modelo de embeddings de RagDocumentEmbeddingServices.
- Usa documentos sintéticos y un proveedor simulado para pruebas reproducibles. Valida Compose desde la raíz y prueba los cambios de acceso con PostgreSQL real.
