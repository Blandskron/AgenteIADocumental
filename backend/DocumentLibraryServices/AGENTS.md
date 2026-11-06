# DocumentLibraryServices

Lee el [contrato y diagnóstico](README.md) y retoma la tarjeta activa del [tablero](../../ROADMAP.md#documentlibraryservices). La configuración, pruebas, acceso e integridad están cubiertos hasta LIB-004. Las siguientes tarjetas refuerzan concurrencia y contratos.

- Comprueba identidad JWT, propiedad de carpeta y permiso documental por separado. Una asociación o favorito nunca concede lectura.
- Contrasta filtros con DocumentSearchServices y DocumentAccessServices. Incluye revocación, columnas canónicas, metadatos históricos y grupos por tenant en listas y conteos.
- Preserva carpetas y favoritos personales. No conviertas administradores documentales en propietarios de bibliotecas ajenas.
- Distingue agregar una asociación de mover todas las asociaciones personales. Prueba reintentos y concurrencia con sesiones independientes.
- Borrar carpetas retira carpetas y asociaciones, nunca documentos ni archivos. Audita relaciones existentes antes de imponer restricciones.
- Preserva las claves compuestas de propietario y el trigger de estructura: ID, propietario y padre de carpeta son inmutables. Los padres se insertan primero. Reubicar carpetas requiere diseño explícito y pruebas de ciclos.
- Las pruebas de migración usan `LIBRARY_TEST_DATABASE_URL` administrativo para bases aisladas con UUID; nunca producción. Monta los scripts SQL en solo lectura y conserva la limpieza de cada base creada por la fixture.
- Al cambiar `document_folder_items`, revisa al escritor de GoogleDriveImportServices. No uses OAuth ni documentos reales para comprobar integridad SQL.
- Al cambiar páginas, respuestas o contadores, actualiza adaptador, hook, DocumentSearchPage y ChatPage juntos. No ocultes incompatibilidades convirtiéndolas en arreglos vacíos.
- Usa PostgreSQL y datos sintéticos. Revierte datos o retíralos por IDs únicos. Separa scripts de código y documentación Markdown.
- Registra comandos y comprobaciones pendientes en la tarjeta. No declares suites o comandos de CI inexistentes. Al cerrar LIB-008, sustituye el diagnóstico pendiente por el contrato final y retira scaffolding sin consumidores.
- Ejecuta `library-tests` sobre PostgreSQL y Ruff antes de cerrar cambios del servicio. Conserva la separación entre vida (`health`) y disponibilidad (`health/db`), y prueba cambios de entorno sin cargar secretos del `.env` raíz.
