# ConversationServices

Lee el [contrato y arranque](README.md) y toma la tarjeta activa del [tablero raíz](../../ROADMAP.md#conversationservices).

- Mantén el filtro por dueño para conversaciones y recursos anidados. Usa identidades emitidas por [AuthServices](../AuthServices/README.md) y revisa el contrato de acceso de [DocumentLibraryServices](../DocumentLibraryServices) al tocar vínculos documentales.
- Comprueba los cambios HTTP con el cliente en `frontend/src`. Usa el [esquema de conversaciones](../../scripts/database/schemas/002_conversations.sql) y PostgreSQL real para pruebas de permisos, claves foráneas y concurrencia.
- Valida Compose desde la raíz y comprueba salud y acceso autenticado según la tarjeta. Usa usuarios y documentos sintéticos.
