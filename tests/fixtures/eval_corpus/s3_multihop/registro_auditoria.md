---
title: Registro de Auditoría Interna
tags: [auditoria, cumplimiento]
aliases: [Registro-Auditoria-Interna]
doc_code: NOTE-S3-04
---

# Registro de Auditoría Interna

La tabla `audit_logs` almacena exclusivamente `actor_user_id`, `tenant_id`, `action`, `resource_type`, `resource_id`, `fingerprint_sha256` y marca de tiempo UTC.

Queda estrictamente prohibido almacenar valores de claves, tokens Bearer o fragmentos de documentos privados en el payload de auditoría. #auditoria
