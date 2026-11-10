# DocumentLibraryServices

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- Comprueba identidad JWT, propiedad de carpeta y permiso documental por separado. Una asociación o favorito nunca concede lectura.
- Reutiliza Identifier y los esquemas de entrada. Valida nombres tras trim, metadatos y cuerpos según README. Mover exige destino explícito; PATCH rechaza cambios nulos o ausentes. Conserva errores sin input, ctx, claves desconocidas o detalles SQL, y no traduzcas errores inesperados a éxitos.
- Contrasta filtros con DocumentSearchServices y DocumentAccessServices. Incluye revocación, columnas canónicas, metadatos históricos y grupos por tenant en listas y conteos.
- Preserva carpetas y favoritos personales. No conviertas administradores documentales en propietarios de bibliotecas ajenas.
- Distingue agregar una asociación de mover todas las asociaciones personales. Prueba reintentos y concurrencia con sesiones independientes.
- Conserva el protocolo compartido con Drive: bloqueo transaccional por usuario/documento, referencia documental, ancestros de raíz a destino y marcadores. Usa altas con conflicto explícito y rollback ante fallos. Prueba esperas reales y liberación de bloqueos también en salidas denegadas.
- Usa `document_library_runtime` y la función acotada de referencia. No concedas UPDATE de documentos al runtime ni membresía del propietario sin login. Al cambiar SQL, revisa permisos, verificador, readiness y pruebas con el login real.
- Borrar carpetas retira carpetas y asociaciones, nunca documentos ni archivos. Audita relaciones existentes antes de imponer restricciones.
- Preserva las claves compuestas de propietario y el trigger de estructura: ID, propietario y padre de carpeta son inmutables. Los padres se insertan primero. Reubicar carpetas requiere diseño explícito y pruebas de ciclos.
- Las pruebas de migración usan `LIBRARY_TEST_DATABASE_URL` administrativo para bases aisladas con UUID; nunca producción. Monta los scripts SQL en solo lectura y conserva la limpieza de cada base creada por la fixture.
- Al cambiar `document_folder_items`, revisa al escritor de GoogleDriveImportServices. No uses OAuth ni documentos reales para comprobar integridad SQL.
- Al cambiar páginas, respuestas o contadores, actualiza adaptador, hook, DocumentSearchPage y ChatPage juntos. No ocultes incompatibilidades convirtiéndolas en arreglos vacíos.
- Conserva páginas con desempate por ID y filtros antes del límite. Los conteos son de documentos visibles; no los sustituyas por metadatos. Prueba consultas por lote, no consultas por documento o carpeta, y el descarte de respuestas obsoletas del controlador web.
- Un favorito ausente en una página parcial no prueba que no exista. Reutiliza los marcadores acotados y privados y comprueba count=0 en altas. Mantén documentado que la interfaz navega raíces y la API admite jerarquía.
- Usa PostgreSQL y datos sintéticos. Revierte datos o retíralos por IDs únicos. Separa scripts de código y documentación Markdown.
- Registra comandos y comprobaciones pendientes en el PR. Mantén README operativo y seguimientos de dependencias e imagen; evita nuevos planes de modernización o capas sin consumidores.
- Ejecuta `library-tests` sobre PostgreSQL y Ruff antes de cerrar cambios del servicio. Conserva la separación entre vida (`health`) y disponibilidad (`health/db`), y prueba cambios de entorno sin cargar secretos del `.env` raíz.
