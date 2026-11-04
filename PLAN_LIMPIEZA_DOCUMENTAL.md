# Limpieza documental aplicada

El proyecto quedo reducido al foco documental.

## Se mantiene

- Autenticacion y perfil: `AuthServices`, `ProfileServices`.
- Nucleo documental: ingestion/embeddings, chat RAG, busqueda, acceso, biblioteca, transferencias, exportaciones e importacion desde Google Drive.
- Conversaciones: se conserva `ConversationServices` para historial del chat documental.
- Frontend simple: login, chat, documentos, carpetas, favoritos, cargas y perfil.
- Docker documental: infraestructura, auth, documents, collaboration, profile y frontend.

## Se retiro

- CRM/workflow.
- WhatsApp.
- Business Intelligence.
- Agentes empresariales y runtime.
- Actividad transversal.
- Notificaciones.
- Pantallas, hooks, APIs, estilos y variables de entorno asociadas a esos modulos.
- Schemas SQL de los dominios retirados.

## Validacion esperada

- `npm run build` en `frontend`.
- `docker compose -f docker/docker-compose.yml config` desde la raiz.
- Arranque del stack con `cd docker && docker compose up --build`.
- Pruebas manuales: login, subir documento, procesar, buscar, preview, descargar, seleccionar para chat, exportar e importar desde Google Drive si hay credenciales.
