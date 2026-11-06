# Trabajar en ProfileServices

Lee [README.md](README.md) para el contrato actual y la evidencia, y [ROADMAP.md](../../ROADMAP.md#profileservices) para elegir la tarjeta. Las instrucciones de [AGENTS raíz](../../AGENTS.md) también aplican. PROFILE-001 es análisis; no confundir decisiones propuestas con garantías implementadas.

## Límites del componente

- Perfil/contacto/avatar pertenecen a este servicio; identidad, credenciales y membresías pertenecen a Auth. No escribir identidad de Auth desde el repositorio de perfiles.
- No asumir que ser administrador de documentos permite leer perfiles personales. La política propuesta por dueño requiere implementación y pruebas en PROFILE-003.
- Revisa juntos rutas, esquemas, caso de uso, repositorio, SQL y consumidores (`features/profile`, `ProfilePage`, `AuthProvider`, `Sidebar`). Una URL de avatar privada requiere adaptar `<img>` mediante el cliente autorizado.
- Antes de cambiar almacenamiento o relaciones, inventaría referencias y huérfanos. No borres uploads ni datos antiguos indiscriminadamente. Conserva rollback, recuperación y compatibilidad explícita.
- JWT de prueba con clave temporal; archivos e identidades sintéticos. No montes uploads reales para ensayar fallos o límites, ni imprimas tokens, `.env`, cuerpos de perfil o claves.

## Verificación

Por ahora están disponibles build, pip check, Ruff y Compose, documentados en README. No existe todavía suite propia de Profile: crearla en PROFILE-002 con PostgreSQL real y agregar casos de cada tarjeta a CI. No sustituir pruebas de concurrencia por una sola sesión o mocks.

Si cambias frontend, ejecuta `npm ci`, `npm test` y `npm run build` desde `frontend`. Si cambias Compose, ejecuta su validación desde la raíz. Registra comandos realmente ejecutados, resultados y pendientes en la tarjeta; no presentes sondas temporales como pruebas permanentes.

Mantén README como entrada humana y este archivo como guía breve. El tablero es la fuente del estado del trabajo. Al cerrar PROFILE-008, reemplaza el diagnóstico histórico por operación final y conserva seguimientos pendientes con evidencia.
