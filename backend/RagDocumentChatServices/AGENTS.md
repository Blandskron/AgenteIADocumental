# RagDocumentChatServices

Lee el [contrato del servicio](README.md) y toma la tarjeta activa del [tablero](../../ROADMAP.md#ragdocumentchatservices).

- Aplica los permisos documentales antes de recuperar fragmentos o construir el contexto enviado a Groq. Revisa tanto las preguntas como los resúmenes y el historial.
- Mantén la compatibilidad con el cliente de chat y con el modelo de embeddings de RagDocumentEmbeddingServices.
- Usa documentos sintéticos y un proveedor simulado para pruebas reproducibles. Valida Compose desde la raíz y prueba los cambios de acceso con PostgreSQL real.
