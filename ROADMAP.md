# Blandskron Documental · Tablero

La demo permite cargar un documento sintético, buscarlo, hacer una pregunta y exportar la respuesta a PDF. `main` contiene la base de portafolio.

Mantén una tarjeta en **En curso**. Pásala a **En revisión** con evidencia y a **Hecha** cuando cumpla sus criterios.

| Estado | ID | Entrega | Evidencia o trabajo pendiente |
|---|---|---|---|
| Hecha | BD-000 | Guía y tablero | Guía de colaboración en AGENTS.md. |
| Hecha | BD-001 | Inventario | Se clasificaron marcas, archivos subidos, metadatos y recursos de terceros. |
| Hecha | BD-002 | Autoría y vía de publicación | Código de Blandskron. El repositorio usa un historial nuevo y reserva los derechos. |
| Hecha | BD-003 | Base reproducible | PR inicial integrado, frontend compilado y stack local sano. |
| Hecha | BD-004 | Identidad Blandskron | Marca aplicada a interfaz, icono, configuración, prompt y PDF. |
| Hecha | BD-005 | Chat con Groq | Respuesta en español verificada por API y en el flujo RAG local. |
| Hecha | BD-006 | Embeddings locales | Modelo real de 384 dimensiones, migración probada en pgvector y documento reindexado. |
| Hecha | BD-007 | CI y prueba integral | PR integrado. Checks de frontend, Compose y migración. Prueba local con dos usuarios y descarga PDF. |
| En revisión | BD-008 | Entrega de portafolio | README y caso sintético listos. Se retiró el acceso a la integración sin implementar. Pendientes la revisión del PR y la decisión de visibilidad. |

## Modernización de servicios

| Estado | Alcance | Evidencia o seguimiento |
|---|---|---|
| Hecha | AuthServices | Cierre integrado en main. Arranque validado sobre base existente, 39 pruebas y OpenAPI sin errores. [Contrato, operación y pruebas](backend/AuthServices/README.md). |
| Seguimiento | Integridad multiempresa | Las escrituras de Auth y la emisión de claims validan relaciones. Falta aplicar restricciones de integridad en PostgreSQL y probar escrituras concurrentes entre sesiones sobre el esquema definitivo. |
| Seguimiento | Imagen base de Auth | Revisar los avisos residuales de Debian al actualizar la imagen base. [Evidencia](backend/AuthServices/docs/TESTS.md#dependencias-e-imagen). |

### ConversationServices

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| En revisión | CONV-001 | Aislar la configuración del contenedor y delimitar CORS | `docker compose -f docker/docker-compose.yml config --quiet` y arranque con PostgreSQL en el puerto local alternativo 55432. Se verificaron siete variables de Compose, la clave pública, salud HTTP y PostgreSQL, respuesta 401 sin token y CORS para dos orígenes locales y uno externo. |
| Lista | CONV-002 | Restaurar y autorizar vínculos documentales | Una prueba con rollback reprodujo `NoReferencedTableError` al guardar el vínculo. Resolver la referencia del ORM, aplicar el contrato de acceso de DocumentLibrary y comprobar vínculos permitidos, denegados, revocados y solicitudes repetidas en PostgreSQL. |
| Lista | CONV-003 | Validar identidad JWT y aislamiento por dueño | Exigir identidad y expiración según AuthServices. Probar el contrato y el acceso cruzado a conversaciones, mensajes y vínculos. |
| Lista | CONV-004 | Limitar escrituras y paginar el historial | Acotar contenido y metadatos, verificar orden estable y adaptar el cliente sin perder acceso al historial existente. |
| Lista | CONV-005 | Restringir acceso a PostgreSQL y cerrar operación | Sustituir el usuario compartido por permisos mínimos, revisar dependencias e imagen y verificar arranque y CI desde una instalación limpia. |

## Validación

- `docker compose -f docker/docker-compose.yml up -d --build --wait` arrancó el stack local. PostgreSQL y los servicios con healthcheck llegaron a estado sano.
- El primer PR se integró en `main`. El PR de validación agrega checks para frontend, Compose y la migración de embeddings sobre PostgreSQL con pgvector.
- `scripts/smoke_documental.ps1` verificó login, carga e indexación, búsqueda, chat con fuente y descarga PDF. Se verificó la reindexación mediante su endpoint y se comprobó con dos usuarios que el observador no puede recuperar el documento privado.
- La prueba SQL usa tablas temporales, cambia un índice de 1536 a 384 dimensiones y verifica que repetir la migración conserva los vectores nuevos.
- El historial alcanzable desde las ramas activas se revisó en busca de las marcas anteriores, claves de Groq, bloques de claves privadas y archivos subidos. Los archivos de entorno locales, documentos, cargas de perfil y claves de autenticación quedan ignorados.

## Criterios de cierre de BD-008

- Una persona puede seguir el README en una instalación limpia y completar el recorrido principal.
- La entrega contiene únicamente código, datos sintéticos y recursos que se pueden compartir. Revisar credenciales, archivos subidos, atribuciones y visibilidad antes de distribuir.
- Mostrar Google Drive como opcional. Para incluirlo en una demo en vivo, validar OAuth con un proyecto de Google de desarrollo.
