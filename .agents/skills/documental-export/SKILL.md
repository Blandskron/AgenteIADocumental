---
name: documental-export
description: "Mantener DocumentExportServices al cambiar su API, persistencia o integración. Genera y almacena el PDF de una instantánea de chat con historial y descarga privados."
---

# documental-export

Lee las [instrucciones del ámbito](../../../backend/DocumentExportServices/AGENTS.md) y abre desde el [README](../../../backend/DocumentExportServices/README.md) la guía del contrato o de operación relevante.

1. Conserva el vínculo opcional a conversaciones y mensajes remotos y el alcance exclusivo del dueño.
2. Revisa clave de operación, cuota, límites y atomicidad de bytes y metadatos.
3. Usa fixtures sintéticos para comprobar texto, glifos y páginas; prueba reintentos en PostgreSQL.
