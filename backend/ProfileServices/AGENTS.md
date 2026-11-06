# Trabajar en ProfileServices

Lee [README.md](README.md) para el contrato actual y la evidencia, y [ROADMAP.md](../../ROADMAP.md#profileservices) para elegir la tarjeta. Las instrucciones de [AGENTS raíz](../../AGENTS.md) también aplican. PROFILE-001 es análisis; no confundir decisiones propuestas con garantías implementadas.

## Límites del componente

- Perfil/contacto/avatar pertenecen a este servicio; identidad, credenciales y membresías pertenecen a Auth. No escribir identidad de Auth desde el repositorio de perfiles.
- La API y el repositorio solo permiten el perfil propio; ningún rol administrativo amplía el dueño. No reintroducir listados globales ni IDs de destino. `/static` sigue público hasta PROFILE-005 y debe migrarse junto al consumidor web.
- Conserva el contrato JWT de Auth y comprueba cuenta activa y huella de contraseña en cada petición; no devuelvas ni registres esa huella. La consulta solo debe devolver un booleano. El contrato HTTP real se prueba con `scripts/profile/verify_auth_contract.py`, además de los JWT sintéticos de la suite.
- Revisa juntos rutas, esquemas, caso de uso, repositorio, SQL y consumidores (`features/profile`, `ProfilePage`, `AuthProvider`, `Sidebar`). Una URL de avatar privada requiere adaptar `<img>` mediante el cliente autorizado.
- Antes de cambiar almacenamiento o relaciones, inventaría referencias y huérfanos. No borres uploads ni datos antiguos indiscriminadamente. Conserva rollback, recuperación y compatibilidad explícita.
- JWT de prueba con clave temporal; archivos e identidades sintéticos. No montes uploads reales para ensayar fallos o límites, ni imprimas tokens, `.env`, cuerpos de perfil o claves.

## Verificación

Ejecuta suite PostgreSQL (`profile-tests`), Ruff, pip check, auditoría (`profile-audit`) y Compose como indica README. Agrega casos mantenidos de cada tarjeta a la suite y CI. No sustituir pruebas de concurrencia por una sola sesión o mocks. La suite exige `PROFILE_TEST_DATABASE_URL`, revierte escrituras y usa storage temporal; no apuntarla a una base de producción.

El entrypoint es `app.main:create_app --factory`. No leer `.env` desde Settings ni introducir efectos de disco/conexiones al importar. Conserva configuración explícita, CORS acotado, validación de clave y preparación/limpieza de recursos en lifespan. Un cambio en salud debe preservar respuestas sin detalles internos.

Si cambias frontend, ejecuta `npm ci`, `npm test` y `npm run build` desde `frontend`. Si cambias Compose, ejecuta su validación desde la raíz. Registra comandos realmente ejecutados, resultados y pendientes en la tarjeta; no presentes sondas temporales como pruebas permanentes.

Mantén README como entrada humana y este archivo como guía breve. El tablero es la fuente del estado del trabajo. Al cerrar PROFILE-008, reemplaza el diagnóstico histórico por operación final y conserva seguimientos pendientes con evidencia.
