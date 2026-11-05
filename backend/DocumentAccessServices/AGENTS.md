# DocumentAccessServices

Lee el [contrato y operación](README.md) y toma la tarjeta activa del [tablero](../../ROADMAP.md#documentaccessservices).

- Comprueba por separado los permisos de lectura, descarga, borrado y gestión de asignaciones.
- Revisa los consumidores de `frontend/src/features/document-access` cuando cambies contratos.
- Usa documentos y archivos sintéticos para probar rutas, borrado y recuperación ante fallos.
- Conserva la coherencia entre asignaciones, eventos, notificaciones y auditoría cuando cambies una escritura.
- Confirma el borrado lógico y la cola de limpieza antes de tocar archivos. Conserva los registros de borrado para autorizar reintentos.
- Prueba recuperación y concurrencia con sesiones independientes. Retira siempre los registros sintéticos confirmados al terminar.
- Valida Compose desde la raíz y registra las comprobaciones pendientes en el tablero.
