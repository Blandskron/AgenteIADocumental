---
name: documental-drive
description: "Mantener GoogleDriveImportServices al cambiar su API, persistencia o integración. Conecta Google Drive mediante OAuth PKCE y coordina importaciones recuperables hacia Ingesta."
---

# documental-drive

Lee las [instrucciones del ámbito](../../../backend/GoogleDriveImportServices/AGENTS.md) y abre desde el [README](../../../backend/GoogleDriveImportServices/README.md) la guía del contrato o de operación relevante.

1. Preserva el intento de OAuth de un solo uso, las versiones de credenciales y los estados de revocación.
2. Registra el intento antes de la carga y conserva resultados ambiguos para revisión; no los repitas a ciegas.
3. Prueba ambas rutas web y las carreras de importación con transporte y credenciales sintéticos.
