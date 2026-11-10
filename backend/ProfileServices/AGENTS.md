# Trabajar en ProfileServices

Lee el [README](README.md), las [reglas raíz](../../AGENTS.md) y la [verificación de entrega](../../docs/release/README.md). Delimita cada cambio en su PR y conserva los contratos vigentes.

## Límites del componente

- Perfil/contacto/avatar pertenecen a este servicio; identidad, credenciales y membresías pertenecen a Auth. No escribir identidad de Auth desde el repositorio de perfiles.
- La API y el repositorio solo permiten el perfil propio; ningún rol administrativo amplía el dueño. No reintroducir listados globales ni IDs de destino. `/static` está retirado. Avatar privado JPEG en PostgreSQL (máximo 1 MiB); lectura propia autenticada y consumidor blob con limpieza.
- Conserva el contrato JWT de Auth y comprueba cuenta activa y huella de contraseña en cada petición; no devuelvas ni registres esa huella. La consulta solo debe devolver un booleano. El contrato HTTP real se prueba con `scripts/profile/verify_auth_contract.py`, además de los JWT sintéticos de la suite.
- Usa `profile_identity_is_current` con el rol `profile_runtime`, sin SELECT directo sobre Auth. Su propietario NOLOGIN conserva el lock de identidad; no ampliar EXECUTE a PUBLIC ni herencia/membresías. Provisiona tras migrar Auth, con el SQL transaccional/verificador. Prueba SET ROLE desde una conexión runtime real: una sesión superusuaria con SET LOCAL ROLE no demuestra su denegación. Mantén los avisos de imagen en docs/IMAGE_AUDIT.json y la verificación de entrega; no ocultar el vendorizado de pip por no ser una distribución instalada.
- GET devuelve la versión y PUT exige `expected_version`: no introducir escrituras ciegas, reintentos automáticos de conflictos ni timestamps como sustituto de la versión. Conserva FOR SHARE de identidad hasta commit/cierre y prueba ambos órdenes frente a revocaciones. Cualquier cambio de campos debe respetar omisión/null/vaciado y los límites documentados.
- Aplica cambios de esquema por `scripts/database/run_all.sql`; ejecuta el preflight agregado antes de migrar. Preserva las filas heredadas y prueba actualización/repetición en esquema anterior. Los tests entre conexiones usan datos sintéticos confirmados mediante commit con limpieza verificada; los demás pueden usar rollback.
- Revisa juntos rutas, esquemas, caso de uso, repositorio, SQL y consumidores (`features/profile`, `ProfilePage`, `AuthProvider`, `Sidebar`). Una URL de avatar privada requiere adaptar `<img>` mediante el cliente autorizado.
- Antes de cambiar almacenamiento o relaciones, inventaría referencias y huérfanos. No borres uploads ni datos antiguos indiscriminadamente. Conserva rollback, recuperación y compatibilidad explícita.
- JWT de prueba con clave temporal; archivos e identidades sintéticos. No montes uploads reales para ensayar fallos o límites, ni imprimas tokens, `.env`, cuerpos de perfil o claves.

## Verificación

Ejecuta suite PostgreSQL (`profile-tests`), Ruff, pip check, auditoría (`profile-audit`) y Compose como indica README. Agrega casos mantenidos de cada cambio a la suite y CI. No sustituir pruebas de concurrencia por una sola sesión o mocks. La suite exige `PROFILE_TEST_DATABASE_URL`, revierte escrituras y usa archivos temporales sintéticos para mantenimiento; no apuntarla a una base de producción.

El entrypoint es `app.main:create_app --factory`. No leer `.env` desde Settings ni introducir efectos de disco/conexiones al importar. Conserva configuración explícita, CORS acotado, validación de clave y preparación/limpieza de recursos en lifespan. Un cambio en salud debe preservar respuestas sin detalles internos.

Si cambias frontend, ejecuta `npm ci`, `npm test`, `npm run build` y `npm run test:browser` desde `frontend` (instala Chromium con `npx playwright install chromium`). Conserva la identidad del cliente durante refresh y el límite por sesión/usuario/tenant; el borrador no debe depender del objeto de usuario renovado. Prueba cambios de sesión, respuestas tardías y carreras de escrituras en el controlador; nunca derives permisos por staff o coincidencias de nombres. Las pruebas de navegador interceptan APIs sintéticas, no sustituyen el contrato HTTP real. Si cambias Compose, ejecuta su validación desde la raíz. Registra comandos realmente ejecutados, resultados y pendientes en el PR; no presentes sondas temporales como pruebas permanentes.

Mantén README como entrada humana y este archivo como guía breve. `app/`, `tests/` y `scripts/profile/` contienen código; `docs/` conserva únicamente evidencia documental. Mantén el README operativo, sin diagnósticos obsoletos, y conserva el inventario/auditoría con el artefacto al que corresponde. No elimines migraciones, preflight, mantenimiento revisado ni pruebas permanentes por haber cerrado la modernización. La verificación de entrega conserva evidencia fechada y disposición de avisos.
