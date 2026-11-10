# Colaborar en DocumentTransferServices

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- El servicio registra un diario del cliente, no transfiere archivos ni acredita su entrega. No conviertas eventos en permisos o auditoría autoritativa.
- Exige access JWT con user_id entero positivo y exp entero vigente. Historial privado incluso para administradores; autoriza cada referencia enviada según Library/Access, sin revelar si un documento ajeno existe.
- Respeta metadata HTTP → metadata_ ORM; ausencia conserva, document_id/size_bytes null retiran y metadata {} vacía. Mantén límites de esquema/cuerpo y errores privados. No uses create_all ni repares datos históricos silenciosamente.
- Conserva transiciones y progreso del dominio, terminales sin reapertura y COMPLETED=100. PATCH idéntico no debe escribir otra vez; POST no se deduplica por nombre.
- Orden: advisory por dueño → documento si se adjunta → evento con FOR UPDATE. La respuesta se captura antes de commit; fallo de commit no devuelve éxito. Limpieza SQL hasta 1000 terminales con contador efectivo, sin borrar documentos/archivos; FK documental con SET NULL.
- Mantén runtime sin UPDATE/DELETE documental y la función de referencia con propietario sin login, tabla cualificada y sin PUBLIC/delegación. Ejecuta verify_role.sql; prueba carreras con conexiones runtime reales y un administrador separado para preparar datos/simular borrados.
- Cambia API paginada, adaptador, controlador/hook/modal y Search/Chat juntos. Conserva generaciones por cliente y flujos compartidos: la cola no bloquea ni repite archivos, conserva su error original y publica advertencias fuera del modal.
- Usa datos y claves sintéticos con rollback o limpieza comprobada. Drift requiere bases aisladas; no alteres ACL compartidas para probar fallos. Audita propietarios históricos con scripts/database/transfer/audit_owners.sql sin reasignarlos por apariencia numérica.
- Desde la raíz ejecuta la etapa Compose transfer-tests y la misma etapa con `ruff check --no-cache app tests`, tras arrancar según README. Para consumidores, `npm ci`, `npm test`, `npm run build` desde frontend. Mantén comandos y evidencia en README/PR.
- Conserva UID 10007, capacidades retiradas, no-new-privileges y herramientas solo en test/audit. Separa auditoría Python de avisos de imagen y conserva los avisos residuales en la evidencia de entrega. Antes de retirar un archivo, verifica imports y consumidores.
