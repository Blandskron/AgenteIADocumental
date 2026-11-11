---
name: documental-auth
description: "Mantener AuthServices al cambiar su API, persistencia o integración. Identidad, sesión JWT RS256, usuarios y administración de membresías de empresa."
---

# documental-auth

Lee las [instrucciones del ámbito](../../../backend/AuthServices/AGENTS.md) y abre desde el [README](../../../backend/AuthServices/README.md) la guía del contrato o de operación relevante.

1. Para login, refresh y cambios de claims, revisa rutas, serializers, usuarios y consumidores JWT en conjunto.
2. Distingue administración global de permisos por empresa y verifica ambas con PostgreSQL.
3. Comprueba el orden de migración, bootstrap e integridad antes de cambiar tablas o claves.
