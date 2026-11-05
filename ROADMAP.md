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
| Hecha | CONV-001 | Aislar la configuración del contenedor y delimitar CORS | PR #16 integrado. Se verificaron siete variables de Compose, la clave pública, salud HTTP y PostgreSQL, respuesta 401 sin token y CORS para dos orígenes locales y uno externo. |
| Hecha | CONV-002 | Restaurar y autorizar vínculos documentales | PR #17 integrado. Cuatro pruebas sobre PostgreSQL cubren permisos, revocación, retiro y concurrencia. |
| Hecha | CONV-003 | Validar identidad JWT y aislamiento por dueño | PR #18 integrado. 20 pruebas sobre PostgreSQL y verificación con tokens de acceso emitidos y renovados por AuthServices. |
| Hecha | CONV-004 | Limitar escrituras y paginar el historial | PR #19 integrado. 28 pruebas con PostgreSQL, índice comprobado, Ruff y compilación del frontend. |
| Hecha | CONV-005 | Restringir acceso a PostgreSQL y cerrar operación | PR #20 integrado. Arranque con volumen nuevo, 28 pruebas, verificación SQL de permisos y aprovisionamiento serializado del esquema compartido. |

Quedan en seguimiento nueve CVE altos de la imagen base Debian sin versión corregida indicada por Trivy. [Evidencia de la imagen](backend/ConversationServices/README.md#dependency-and-image-checks).

### RagDocumentChatServices

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| Hecha | RAG-001 | Aislar configuración, CORS y acceso HTTP | PR #21 integrado. Compose válido, arranque local, CORS, rechazo de la clave interna anterior y sonda de Groq. |
| Hecha | RAG-002 | Validar identidad y permisos documentales | PR #22 integrado. JWT, revocación en preguntas y resúmenes e historial verificados con 12 pruebas sobre PostgreSQL y pgvector. |
| Hecha | RAG-003 | Acotar solicitudes, contexto e historial | PR #23 integrado. 24 pruebas con PostgreSQL y pgvector cubrieron límites, separación de sesiones y persistencia ante fallos. |
| Hecha | RAG-004 | Probar la integración con Groq | PR #24 integrado. CI incluye diez pruebas del contrato HTTP simulado. La prueba con Groq real requiere una clave configurada. |
| Hecha | RAG-005 | Restringir PostgreSQL y cerrar operación | PR #25 integrado con seis checks verdes. Arranque en volumen nuevo, 34 pruebas con PostgreSQL y modelo CPU validado con 384 dimensiones. [Auditoría y seguimiento](backend/RagDocumentChatServices/README.md#verificación-de-la-imagen). |

### RagDocumentEmbeddingServices

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| Hecha | EMB-001 | Aislar configuración y validar arranque | PR #26 integrado. Compose, arranque, CORS y configuración de fragmentación verificados. |
| Hecha | EMB-002 | Validar identidad y permisos de ingesta | PR #27 integrado. Nueve pruebas con PostgreSQL y comprobación HTTP con tokens reales de AuthServices. |
| Hecha | EMB-003 | Limitar archivos y confinar su lectura | PR #28 integrado. Arranque y 18 pruebas verificaron límites multipart, limpieza, confinamiento y extracción. |
| Hecha | EMB-004 | Hacer reproducible la indexación | PR #29 integrado. 23 pruebas con PostgreSQL y verificación del modelo real de 384 dimensiones. |
| Hecha | EMB-005 | Restringir PostgreSQL y cerrar operación | PR #30 integrado con seis checks verdes. 23 pruebas y carga y reindexación HTTP con un vector real de 384 dimensiones. [Auditoría de imagen](backend/RagDocumentEmbeddingServices/README.md#verificación-de-la-imagen). |

Quedan en seguimiento los CVE de Debian 13.7 que Trivy detectó en la imagen de ingesta, incluido CVE-2026-6653 en libxml2. [Evidencia de la imagen](backend/RagDocumentEmbeddingServices/README.md#verificación-de-la-imagen).

### DocumentSearchServices

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| Hecha | SEARCH-001 | Aislar configuración y comprobar arranque | PR #31 integrado. Compose, arranque, CORS y búsqueda con JWT real de AuthServices verificados. |
| Hecha | SEARCH-002 | Aplicar permisos en todas las rutas | PR #32 integrado. Compose, Ruff, 10 pruebas con PostgreSQL y pgvector, y acceso verificado con un JWT real de AuthServices. |
| Hecha | SEARCH-003 | Acotar y estabilizar las consultas | PR #33 integrado con seis checks aprobados. OpenAPI y 18 pruebas verificaron los límites, la paginación y el número de consultas. |
| Hecha | SEARCH-004 | Revisar el contrato de respuesta | PR #34 integrado con seis checks aprobados. La prueba HTTP comprueba extractos, errores, selección y exclusión de datos internos. |
| Hecha | SEARCH-005 | Restringir PostgreSQL y cerrar operación | PR #35 integrado con seis checks aprobados. Arranque con volúmenes nuevos, aprovisionamiento repetido, permisos SQL y 26 pruebas verificados. |

Quedan en seguimiento diez CVE altos únicos de Debian sin versión corregida indicada por Trivy y un aviso asociado a los metadatos internos de pip. [Evidencia de la imagen](backend/DocumentSearchServices/README.md#verificación-de-la-imagen).

### DocumentAccessServices

La revisión inicial abarcó rutas, JWT, repositorio, resolución de archivos, asignaciones, notificaciones y consumidores web. El servicio carga el entorno global, acepta CORS abierto y comprueba solo salud HTTP al arrancar. Los permisos de lectura incluyen asignaciones canceladas y grupos sin alcance de tenant. El borrado reutiliza permisos de lectura y elimina el archivo antes de confirmar PostgreSQL. Las asignaciones guardan estado, eventos, notificaciones y auditoría en commits separados. Las siguientes tarjetas cubren estos recorridos por incrementos.

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| Hecha | ACCESS-001 | Aislar configuración y comprobar arranque | PR #36 integrado con seis checks aprobados. Configuración explícita, CORS local y arranque con PostgreSQL, almacenamiento y clave pública verificados. |
| Hecha | ACCESS-002 | Unificar identidad y permisos de lectura | PR #37 integrado con seis checks aprobados. 22 pruebas HTTP verificaron JWT, tenant, grupos, revocación y permisos específicos de descarga. |
| Hecha | ACCESS-003 | Confinar lectura y servir archivos | PR #38 integrado con seis checks aprobados. 56 pruebas del backend, compilación y lector de nombres Unicode del frontend verificados. Persisten cuatro alertas altas de npm. |
| Hecha | ACCESS-004 | Autorizar y hacer recuperable el borrado | PR #39 integrado con seis checks aprobados. 71 pruebas, Compose, arranque, esquema repetido y Ruff verificados. Cubren permisos, cascadas, fallos, reintentos, enlaces, referencias compartidas, recuperación automática y sesiones concurrentes. |
| Hecha | ACCESS-005 | Hacer consistentes las asignaciones | PR #40 integrado con seis checks aprobados. 116 pruebas PostgreSQL, Ruff, Compose y arranque saludable. Roles y destinatarios vigentes, transiciones explícitas, reintentos idempotentes y transacciones con concurrencia y fallos inyectados verificados. |
| En revisión | ACCESS-006 | Acotar entradas y revisar respuestas | Límites de IDs, motivos, firmas, JSON y cuerpo HTTP. Cuatro listas paginadas con desempate por ID y frontend con Cargar más. `access-tests python -m pytest -q -p no:cacheprovider --tb=short tests` aprobó 165 pruebas; Ruff, Compose y arranque reconstruido saludables. `npm ci`, `npm test` (7 pruebas) y `npm run build` aprobados. Persisten cuatro alertas altas de npm registradas. Contrato, errores sin valores enviados, UTC y documentación actualizados. Pendiente revisión del PR. |
| Lista | ACCESS-007 | Restringir PostgreSQL y cerrar operación | Rol con permisos mínimos, imagen sin privilegios, dependencias auditadas, pruebas en CI y arranque limpio. Actualizar documentación y registrar seguimiento. |

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
