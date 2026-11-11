---
name: documental-transfer
description: "Mantener DocumentTransferServices al cambiar su API, persistencia o integración. Registra el historial privado de cargas y descargas que comunica la web."
---

# documental-transfer

Lee las [instrucciones del ámbito](../../../backend/DocumentTransferServices/AGENTS.md) y abre desde el [README](../../../backend/DocumentTransferServices/README.md) la guía del contrato o de operación relevante.

1. Preserva las transiciones terminales y las actualizaciones idempotentes; un evento describe el cliente y no concede acceso.
2. Conserva el orden de locks y el alcance de la función de referencias documentales.
3. Verifica que el fallo del diario no repita ni bloquee la transferencia y que la limpieza conserve activos.
