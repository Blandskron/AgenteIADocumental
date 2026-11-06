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
- Desde la raíz ejecuta `docker compose -f docker/docker-compose.yml run --build --rm --no-deps transfer-tests` y la misma etapa con `ruff check --no-cache app tests`, tras arrancar el servicio según README. Las pruebas requieren TRANSFER_TEST_DATABASE_URL explícita, usan tablas temporales o rollback y claves sintéticas. No cargues .env automáticamente ni inyectes el entorno global en Compose. Al cierre retira scaffolding sin consumidores y deja README operativo, sin duplicar planes de modernización.
