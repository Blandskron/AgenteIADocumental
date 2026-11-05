# DocumentSearchServices

Lee el [contrato HTTP](README.md) y toma la tarjeta activa del [tablero](../../ROADMAP.md#documentsearchservices).

- Aplica los permisos antes de devolver resultados, conteos, fragmentos, snippets o selecciones para el chat.
- Revisa los consumidores en `frontend/src/features/document-search` si cambias filtros, orden, paginación o campos de respuesta.
- Usa documentos y usuarios sintéticos para probar acceso, revocación y consultas en PostgreSQL. Valida Compose desde la raíz.
- Ejecuta las pruebas con `search-tests`. Si cambias las columnas que consulta el servicio, revisa los permisos de `document_search_runtime` en [los scripts SQL](../../scripts/database/search).
