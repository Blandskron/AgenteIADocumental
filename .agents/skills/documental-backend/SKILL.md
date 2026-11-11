---
name: documental-backend
description: "Coordinar contratos, permisos o cambios de despliegue que cruzan varios servicios del backend documental."
---

# documental-backend

Lee las [instrucciones del ámbito](../../../backend/AGENTS.md) y abre desde el [README](../../../backend/README.md) la guía del contrato o de operación relevante.

1. Rastrea quién posee el dato y qué APIs, jobs y clientes consumen el contrato antes de modificarlo.
2. Distingue la comprobación de identidad vigente por HTTP de las funciones SQL acotadas que usan algunos servicios.
3. Para cambios de esquema o permisos verifica roles runtime y la coordinación de migración, API y frontend.
