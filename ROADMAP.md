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

La modernización de rutas, JWT, permisos, archivos, asignaciones, notificaciones y consumidores web está integrada. El servicio usa configuración explícita, rol acotado, transacciones y borrado recuperable. El README registra el contrato operativo y el seguimiento de la imagen base.

| Estado | ID | Entrega | Criterio de aceptación |
|---|---|---|---|
| Hecha | ACCESS-001 | Aislar configuración y comprobar arranque | PR #36 integrado con seis checks aprobados. Configuración explícita, CORS local y arranque con PostgreSQL, almacenamiento y clave pública verificados. |
| Hecha | ACCESS-002 | Unificar identidad y permisos de lectura | PR #37 integrado con seis checks aprobados. 22 pruebas HTTP verificaron JWT, tenant, grupos, revocación y permisos específicos de descarga. |
| Hecha | ACCESS-003 | Confinar lectura y servir archivos | PR #38 integrado con seis checks aprobados. 56 pruebas del backend, compilación y lector de nombres Unicode del frontend verificados. Persisten cuatro alertas altas de npm. |
| Hecha | ACCESS-004 | Autorizar y hacer recuperable el borrado | PR #39 integrado con seis checks aprobados. 71 pruebas, Compose, arranque, esquema repetido y Ruff verificados. Cubren permisos, cascadas, fallos, reintentos, enlaces, referencias compartidas, recuperación automática y sesiones concurrentes. |
| Hecha | ACCESS-005 | Hacer consistentes las asignaciones | PR #40 integrado con seis checks aprobados. 116 pruebas PostgreSQL, Ruff, Compose y arranque saludable. Roles y destinatarios vigentes, transiciones explícitas, reintentos idempotentes y transacciones con concurrencia y fallos inyectados verificados. |
| Hecha | ACCESS-006 | Acotar entradas y revisar respuestas | PR #41 integrado con seis checks aprobados. 165 pruebas backend, 7 frontend, Ruff, Compose y arranque verificados. Páginas con orden estable, límites HTTP y errores sin reflejar valores enviados. |
| Hecha | ACCESS-007 | Restringir PostgreSQL y cerrar operación | PR #42 integrado con seis checks aprobados. 184 pruebas con rol restringido, Ruff, Compose, arranque limpio, provisionamiento repetido y limpieza automática verificados. Auditoría Python sin avisos; seguimiento de Debian en ACCESS-F01. |

### Seguimiento de la imagen de acceso

| Estado | ID | Tarea | Evidencia y siguiente acción |
| --- | --- | --- | --- |
| Seguimiento | ACCESS-F01 | Reevaluar los avisos de Debian al reconstruir | Trivy 0.74.0, 5 de noviembre de 2026, reportó 46 coincidencias altas por paquete, 10 CVE distintos, cero críticos y sin versiones corregidas indicadas. El README de DocumentAccessServices registra imagen, CVE y alcance. Reconstruir y reevaluar al actualizar la base, registrando correcciones o aceptación explícita del riesgo antes de un despliegue público. Las dependencias Python del runtime no reportaron avisos con pip-audit. |

### DocumentLibraryServices

| Estado | ID | Tarea | Criterios de aceptación |
| --- | --- | --- | --- |
| Hecha | LIB-001 | Analizar contratos, aislamiento y operación | PR #43 integrado con seis checks aprobados. Doce operaciones revisadas, trece observaciones sintéticas confirmadas, línea base de dependencias y ocho incrementos documentados en README, AGENTS y tablero. |
| Hecha | LIB-002 | Aislar configuración y establecer pruebas | PR #44 integrado con seis checks aprobados. Diez variables explícitas, CORS local, readiness de clave y seis tablas, pool acotado, cierre fiable y 49 pruebas PostgreSQL con Ruff y Compose. |
| Hecha | LIB-003 | Validar identidad y unificar permisos | PR #45 integrado con seis checks aprobados. 92 pruebas backend y 10 frontend verifican JWT, lectura coherente, revocación, precedencia canónica, grupos por tenant, privacidad y conteos. |
| Hecha | LIB-004 | Reforzar integridad de carpetas y asociaciones | PR #46 integrado con seis checks aprobados. 112 pruebas Library y 8 Drive con PostgreSQL, Ruff, 14 pruebas frontend, npm ci/build y Compose aprobados. Arranque limpio y esquema repetido sin anomalías. Auditoría previa sin borrados, claves de propietario, estructura inmutable sin ciclos, índices existentes con HTTP 409 y advertencias de asociación visibles. Cuatro alertas altas npm en seguimiento. |
| Hecha | LIB-005 | Hacer idempotentes y concurrentes las escrituras | 140 pruebas Library y 9 Drive con PostgreSQL, Ruff en ambos servicios, Compose y arranque aprobados. Altas con conflicto idempotente, retiradas SQL, movimientos serializados por usuario/documento y ancestros bloqueados desde la raíz. Sesiones independientes comprueban esperas reales, destino nulo, independencia, cascadas y rollback con recuperación de sesión. Comandos: library-tests, drive-tests, ruff check --no-cache app tests, config --quiet y up -d --build --wait document-library-service. PR #47 integrado con seis checks aprobados. Desplegar Library y Drive juntos; rol mínimo con bloqueo acotado pendiente de LIB-008. |
| Hecha | LIB-006 | Acotar entradas y estabilizar errores | 239 pruebas Library con PostgreSQL, Ruff, OpenAPI, Compose y arranque aprobados. IDs de 1 a 128, nombres de 1 a 200 tras trim, metadatos de 16 KiB y 16 niveles, cuerpo de 64 KiB contado por fragmentos. Movimientos con destino explícito y PATCH sin cambios nulos; errores privados 400/404/409/413/422 y SQL 500 genérico con rollback. Comandos: library-tests, ruff check --no-cache app tests, config --quiet y up -d --build --wait document-library-service. Fronteras, ausencia de escrituras y recuperación de sesión verificadas. Consumidores revisados; PR #48 integrado con seis checks aprobados. |
| Hecha | LIB-007 | Paginar y revisar el contrato con la interfaz | 275 pruebas Library y 29 frontend; Ruff, npm ci/test/build, Compose y arranque aprobados. Cuatro listados paginados con desempate por ID, conteos por lote y marcadores privados acotados. Controladores por cliente descartan respuestas tardías y conservan errores; carga incremental, count=0, revocación y conflictos cubiertos. Se retiran consultas por carpeta, métricas ficticias y peticiones de Chat sin consumidor. README documenta raíces en web, jerarquía en API y límites de offset sin instantánea entre páginas. PR #49 integrado con seis checks aprobados. Desplegar frontend y Library juntos. Persisten cuatro alertas altas npm en seguimiento. |
| En revisión | LIB-008 | Restringir ejecución y cerrar el servicio | Rol mínimo repetible y función de referencia con propietario sin login; documentos sin UPDATE/DELETE para runtime. UID 10006, herramientas separadas, dependencias actualizadas y pip-audit sin avisos instalados. Suite y regresiones suman 292 casos, incluidos HTTP y concurrencia con login real, permisos negativos, drift y readiness. Ruff, Compose, arranque limpio/existente, rol repetido y pip check verificados. Se retiran seis archivos sin consumidores, errores sobrantes y diagnóstico histórico; README/AGENTS quedan operativos. CI y revisión del PR pendientes. Avisos de imagen registrados en LIB-F01/F02. |

### Seguimiento de la imagen de Library

| Estado | ID | Tarea | Evidencia y siguiente acción |
| --- | --- | --- | --- |
| Seguimiento | LIB-F01 | Reevaluar Debian al actualizar la base | Trivy 0.74.0, 6 de noviembre de 2026: 46 coincidencias altas, diez CVE únicos de Debian 13.7, cero críticos y sin versiones corregidas indicadas. Reconstruir con --pull, repetir escaneo y revisar antes de despliegue público. [Inventario y evidencia](backend/DocumentLibraryServices/README.md#verificación-de-dependencias-e-imagen). |
| Seguimiento | LIB-F02 | Reevaluar setuptools vendorizado por pip | Trivy reporta CVE-2025-47273 en la copia 70.3.0; indica 78.1.1 para el paquete. No hay distribución setuptools instalada; pip 26.3 y el wheel de ensurepip mantienen esa declaración vendorizada. Revisar actualización upstream y repetir Trivy; no ocultar el aviso ni asumir que instalar otro setuptools reemplaza la copia. [Alcance](backend/DocumentLibraryServices/README.md#verificación-de-dependencias-e-imagen). |

### DocumentTransferServices

| Estado | ID | Tarea | Criterios de aceptación |
| --- | --- | --- | --- |
| Lista | TRANSFER-001 | Analizar contratos, permisos y operación | Inventariar rutas, escrituras de historial, consumidores y retención; revisar identidad, aislamiento, consistencia con cargas/descargas, configuración, dependencias y ejecución. Documentar evidencia sintética y próximos incrementos antes de modificar contratos. Iniciar después de integrar el cierre de Library. |

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
