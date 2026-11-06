# DocumentTransferServices

Lee el [contrato y diagnóstico](README.md) y retoma la tarjeta del [tablero](../../ROADMAP.md#documenttransferservices). TRANSFER-001 documenta la base; las correcciones deben aportar evidencia antes de cambiar contratos.

- El servicio registra historial; no transfiere archivos ni acredita que el navegador los recibió. No conviertas un evento en permiso documental ni en auditoría autoritativa.
- Separa identidad canónica, propiedad del evento y acceso a la referencia documental. Conserva historial privado incluso para administradores; trata referencias ajenas como inexistentes.
- `metadata` HTTP debe mapearse a `metadata_` en SQLAlchemy. Diferencia campos ausentes y nulos; comprueba round trip real en PostgreSQL.
- La FK de `transfer_events.document_id` existe en el esquema compartido y usa SET NULL. No deduzcas su ausencia del comentario del modelo ORM ni uses create_all como migración.
- Mantén documentos y archivos al borrar historial. Audita datos existentes antes de cambiar restricciones o reparar propietarios históricos.
- Revisa estados y progreso junto con DocumentSearchPage y useDocumentQuestionFlow. Los porcentajes actuales representan etapas; no son progreso medido en bytes.
- Un fallo del historial no debe ocasionar repetir una operación documental ya realizada ni ocultar el error original. Conserva advertencias visibles y procesos activos al limpiar.
- Al cambiar respuestas, revisa adaptador, useTransfers, TransferModal, DocumentSearchPage y ChatPage. No conviertas contratos incompatibles en listas vacías; prueba respuestas tardías y cambio de cliente.
- Usa claves, documentos y registros sintéticos. Registra rollback o limpieza por IDs explícitos; las pruebas concurrentes requieren sesiones independientes.
- Establece los comandos de pruebas en TRANSFER-002; no declares existente una suite o job que aún no está implementado. Al cierre retira scaffolding sin consumidores y deja README operativo, sin duplicar planes de modernización.
