# Colaborar en AuthServices

Lee las [reglas globales](../../AGENTS.md), el [README del servicio](README.md) y el [tablero del repositorio](../../ROADMAP.md). Mantén el cambio dentro del servicio salvo dependencias de contrato verificadas.

- Revisa `users/urls.py`, `users/views.py` y `users/serializers.py` juntos cuando cambien permisos. Confirma la separación entre administración global y por empresa.
- Consulta `users/models.py` y [el esquema de empresas](../../scripts/database/schemas/003_tenants.sql) antes de cambiar modelos o relaciones. Las tablas multiempresa se gestionan en SQL.
- Antes de cambiar claims, expiración o claves JWT, identifica consumidores y prueba compatibilidad. Trabaja con usuarios y claves de prueba.
- Usa PostgreSQL para pruebas de autorización y persistencia. La prueba general de la demo está descrita en el [README raíz](../../README.md). Registra comandos, resultados y limitaciones en la tarjeta.
- Carga bajo demanda el [contrato de API](docs/API.md), las [guías de operación](docs/OPERATIONS.md) y los [comandos de verificación](docs/TESTS.md).
