# DocumentSearchServices

Skill del componente: [documental-search](../../.agents/skills/documental-search/SKILL.md).

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- Aplica los permisos antes de devolver resultados, conteos, fragmentos, snippets o selecciones para el chat.
- Revisa los consumidores en `frontend/src/features/document-search` si cambias filtros, orden, paginación o campos de respuesta.
- Usa documentos y usuarios sintéticos para probar acceso, revocación y consultas en PostgreSQL. Valida Compose desde la raíz.
- Ejecuta las pruebas con `search-tests`. Si cambias las columnas que consulta el servicio, revisa los permisos de `document_search_runtime` en [los scripts SQL](../../scripts/database/search).
