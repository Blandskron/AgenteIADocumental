# Colaborar en el esquema compartido

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

- Antes de imponer una relación revisa todos los escritores, los modelos no gestionados de Auth, lectores/helper roles y acciones de borrado. Una comprobación HTTP no sustituye una restricción concurrente de PostgreSQL.
- Preflights en `checks/` deben ser de solo lectura, acotados y agregados; no devolver IDs, nombres, metadata o secretos ni incluir reparaciones implícitas. No incorporarlos al bootstrap antes de que existan sus tablas dependientes.
- No corregir, borrar ni reasignar históricos para hacer pasar una migración. Mantener un inventario privado, una disposición explícita y una aplicación transaccional/revisada; registrar pendientes en la issue o el PR.
- Para DDL mantener orden, preflight, repetibilidad y detección de deriva. No descartar restricciones homónimas inesperadas ni conceder permisos amplios a roles de ejecución.
- Ejecutar SQL de `tests/` únicamente sobre un proyecto/DB sintético dedicado. Las fixtures que simulan datos rotos deben quedar en una transacción sin confirmar y terminar con ROLLBACK; verificar conteos finales antes de retirar sus volúmenes.
- Registrar comandos y alcance real. un diagnóstico de solo lectura no sustituye migraciones validadas ni carreras con conexiones y logins reales.
