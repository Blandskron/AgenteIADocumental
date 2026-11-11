---
name: documental-database
description: "Cambiar migraciones, restricciones multiempresa o permisos de roles PostgreSQL del esquema documental."
---

# documental-database

Lee las [instrucciones del ámbito](../../../scripts/database/AGENTS.md) y abre desde el [README](../../../scripts/database/README.md) la guía del contrato o de operación relevante.

1. Localiza escritores, dependencias de arranque y acciones de borrado en el mapa operativo antes de editar DDL.
2. Comprueba datos heredados con el preflight de solo lectura. Conserva los históricos ante inconsistencias y prueba repetición sobre un esquema anterior.
3. Verifica restricciones concurrentes mediante conexiones reales con los roles runtime y fixtures sintéticos en una base aislada.
