---
title: Procedimiento de Revocación de Emergencia
tags: [seguridad, incidentes, revocacion]
aliases: [Procedimiento-Revocacion-Emergencia]
doc_code: NOTE-S3-03
---

# Procedimiento de Revocación de Emergencia

Ante una sospecha de compromiso de credencial externa (por ejemplo una API key de proveedor LLM), el administrador debe:

1. Ejecutar `DELETE /api/integrations/groq/credentials/` en menos de **15 minutos**.
2. Confirmar que el estado del proveedor pase a `not_configured` y que los embeddings locales sigan operativos.
3. Registrar el código de incidente `INC-REV-900` en [[Registro-Auditoria-Interna]].
