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
