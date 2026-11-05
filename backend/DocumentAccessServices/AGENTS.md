# DocumentAccessServices

Lee el [contrato y operación](README.md) y toma la tarjeta activa del [tablero](../../ROADMAP.md#documentaccessservices).

- Comprueba por separado los permisos de lectura, descarga, borrado y gestión de asignaciones.
- Revisa los consumidores de `frontend/src/features/document-access` cuando cambies contratos.
- Conserva la envoltura de páginas `items`, `limit`, `offset`, `has_more`, los límites HTTP y el desempate por ID. No incluyas entradas recibidas en los errores de validación.
- Usa documentos y archivos sintéticos para probar rutas, borrado y recuperación ante fallos.
- Conserva la coherencia entre asignaciones, eventos, notificaciones y auditoría cuando cambies una escritura.
- Para mutar asignaciones, bloquea primero el documento y después la asignación. Mantén los helpers de eventos, notificaciones y auditoría sin commits internos. Consulta las cuentas y membresías vigentes para autorizar escrituras.
- Confirma el borrado lógico y la cola de limpieza antes de tocar archivos. Conserva los registros de borrado para autorizar reintentos.
- Prueba recuperación y concurrencia con sesiones independientes. Retira siempre los registros sintéticos confirmados al terminar.
- Valida Compose desde la raíz y registra las comprobaciones pendientes en el tablero.
- Ejecuta las operaciones de aplicación con `document_access_runtime`. Reserva `ACCESS_TEST_DATABASE_URL` para preparar, inspeccionar y retirar registros sintéticos. Conserva los bloqueos de autoridad en las funciones SQL con propietario sin login.
- Mantén pruebas, auditoría y ejecución en etapas Docker separadas. Comprueba `access-audit` y los permisos SQL antes de cerrar cambios de dependencias o persistencia.
