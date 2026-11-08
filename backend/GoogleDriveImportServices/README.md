# GoogleDriveImportServices

Microservicio responsable de conectar Google Drive con la biblioteca documental de Blandskron Documental.

**Estado:** DRIVE-001 es el diagnóstico, no el cierre del servicio. La implementación actual conserva deuda de identidad, OAuth, límites y operación. Las mejoras están en el [tablero](../../ROADMAP.md#googledriveimportservices); la [guía para agentes](AGENTS.md) delimita contratos y pruebas. [BASELINE.json](docs/BASELINE.json) identifica la revisión y la evidencia sintética.

## Responsabilidad

- Generar la URL OAuth para conectar una cuenta Google.
- Guardar tokens OAuth cifrados por usuario.
- Refrescar access tokens cuando expiran.
- Descargar archivos seleccionados desde Google Drive.
- Exportar archivos nativos de Google Workspace; la conversión elegida debe ser admitida por la ingesta.
- Enviar los archivos importados a `RagDocumentEmbeddingServices` para que entren al flujo normal de documentos, procesamiento y embeddings.
- Registrar el historial de importaciones y el estado por archivo.

## Puerto

```text
8017 -> 8000
```

## Variables principales

```text
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_DRIVE_REDIRECT_URI=http://localhost:3000/documents
GOOGLE_TOKEN_ENCRYPTION_KEY=change-me-with-a-long-random-secret
RAG_DOCUMENT_BASE_URL=http://localhost:8003
```

En Docker, `RAG_DOCUMENT_BASE_URL` apunta a:

```text
http://rag-document-embedding-service:8000
```

## Endpoints

```text
GET  /api/v1/health
GET  /api/v1/google-drive/auth-url
POST /api/v1/google-drive/oauth/callback
GET  /api/v1/google-drive/connection
POST /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports
GET  /api/v1/google-drive/imports/{import_id}
GET  /api/v1/google-drive/imports/{import_id}/files
```

## Flujo recomendado

1. El frontend obtiene `authorization_url`.
2. El usuario conecta Google Drive.
3. El frontend recibe un `code` OAuth y lo envía al callback del microservicio.
4. El frontend abre Google Picker con la misma aplicación OAuth.
5. El frontend envía los `file_id` seleccionados a `/google-drive/imports`.
6. El microservicio descarga o exporta cada archivo.
7. El microservicio sube cada archivo a `RagDocumentEmbeddingServices`.
8. Los documentos quedan disponibles en la biblioteca documental de Blandskron Documental.

## Formatos nativos de Google

```text
Google Docs   -> DOCX
Google Sheets -> XLSX
Google Slides -> PPTX
Google Drawing -> PDF
```

Estos son los formatos que solicita el cliente actual, no una garantía de procesamiento. Embedding admite PDF/DOCX y otros formatos de su contrato, pero no XLSX/PPTX. DRIVE-005 debe elegir una conversión compatible para Sheets/Slides o rechazarlos explícitamente antes de descargar; no basta con que Google complete la exportación.

## Seguridad

- Requiere JWT de Blandskron Documental en todos los endpoints de usuario.
- Usa `drive.file` como scope recomendado.
- Cifra access token y refresh token antes de persistirlos.
- No expone archivos públicamente; todo entra al pipeline documental interno.

## Carpeta destino y resultados parciales

LIB-004 comprueba que `folder_id` pertenezca al usuario antes de consultar OAuth o descargar archivos. Una carpeta ajena o inexistente devuelve 404. El repositorio repite la comprobación al asociar y PostgreSQL exige que carpeta y asociación tengan el mismo propietario.

LIB-005 coordina el alta con los movimientos y retiradas de Library. Después de cargar el documento, toma el mismo bloqueo transaccional por usuario/documento, protege la referencia documental y bloquea la carpeta y sus ancestros desde la raíz. Inserta con conflicto idempotente y confirma. No mantiene bloqueos durante OAuth, descarga ni carga. Consulta el [protocolo de Library](../DocumentLibraryServices/README.md#escrituras-y-concurrencia) antes de cambiar este escritor y despliega ambos servicios juntos, sin escritores antiguos en paralelo.

Si el documento se importa pero la asociación falla, conserva el documento y su ID. El archivo queda `COMPLETED` con advertencia en `error_message` y `metadata.folder_association.status: FAILED`; la importación queda `PARTIAL`, con un mensaje genérico. `processed_files` incluye ese documento y `failed_files` cuenta los fallos de descarga o carga. Una asociación exitosa registra `metadata.folder_association.status: COMPLETED`. Sin carpeta seleccionada no se registra este resultado.

DocumentSearchPage muestra el mensaje de la importación parcial después de refrescar la biblioteca. Revisa los documentos antes de reintentar: repetir la importación podría crear otro documento. No se reintenta automáticamente una carga ya completada.

## Pruebas del escritor de carpetas

Con PostgreSQL y `database-schema` iniciados, ejecuta desde la raíz:

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps drive-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps drive-tests ruff check --no-cache app tests
```

Las pruebas usan registros sintéticos con IDs únicos y limpieza explícita, PostgreSQL real y un proveedor simulado. No requieren OAuth ni descargan documentos. Cubren propiedad, inserción idempotente, espera real sobre el bloqueo compartido y fallos de asociación, incluido un resultado de carga sin ID documental. Este alcance coordina el escritor con Library; no constituye el cierre de modernización de GoogleDriveImportServices.

## Diagnóstico DRIVE-001

Revisión de `e20052ba1d1b399091ddda1ed1ebee762d2289f4`, el 8 de noviembre de 2026. Se leyeron los 39 archivos rastreados del servicio y se contrastaron los consumidores web, Auth, Library, ingesta, Compose y SQL. Auditoría estática con revisiones independientes y validación del padre: tres hallazgos medios y uno bajo condicionado. No se usaron OAuth, claves ni documentos reales ni se intentó agotar memoria. No se cambió el runtime en este incremento.

| Frontera | Comportamiento comprobado | Mejora y aceptación |
| --- | --- | --- |
| Identidad | JWT firmado y access, sin cuenta activa/huella vigente; dueño con fallback. Firma, expiración y consultas por dueño sí existen. | DRIVE-003: identidad canónica, revocación y dependencia de Auth saneada antes de Google. No se demostró falsificación de JWT ni impersonación por el fallback. |
| OAuth | `auth_url` devuelve state como JSON base64; callback y ambas páginas envían solo code, sin intento almacenado/consumido. La navegación a la página real hace que la web aporte el JWT. | DRIVE-004: intento ligado a identidad/navegador, state aleatorio corto y de un uso antes del canje, PKCE validado para el flujo elegido, pruebas de ausencia/cruce/caducidad/replay. No se demostró exposición del Drive original de la víctima. |
| Cifrado/renovación | Fernet cifra tokens; clave vacía activa constante pública. Refresh conserva token omitido, pero reconnect puede reemplazarlo por null; falta versión frente a refresh concurrente. | DRIVE-004: configuración que falla cerrado, clave independiente/versionada, rotación/reautorización y desconexión revisadas. El fallo de confidencialidad exige además leer ciphertext de una instalación con fallback, no un acceso API anónimo. |
| Descarga | `Client.get` y `response.content` cargan todo; tamaño de metadata no se limita. El máximo 20 MiB de ingesta llega después. | DRIVE-005: cota de bytes reales durante streaming, presupuesto total, exportaciones, spool/cleanup y concurrencia. Timeout de 90 s y lote de 25 no sustituyen una cota de memoria. |
| Persistencia | Import, archivos y finalización confirman por separado; sin clave de operación, lease o reconciliación. Fallos fuera del try por archivo pueden conservar RUNNING. | DRIVE-005/006: estados y recuperación explícitos, operación idempotente y tratamiento de upload ambiguo que no duplique documentos. No confundir ON CONFLICT de carpeta con idempotencia de importación. |
| Historial/web | Lista limitada sin cursor/desempate; archivos sin paginación. Cliente cambia durante refresh; callbacks/Picker/importaciones no tienen la coordinación estable de Profile/Export. | DRIVE-006: contrato paginado y cliente con generación/abort por cuenta/tenant/desmontaje, cancelación/doble envío/reintento, errores y accesibilidad; Node/Chromium. |
| Permisos/tenant | Estado Drive pertenece al usuario; no hay tenant en sus tablas ni validación backend de use_google_drive. Ingesta aplica por separado permiso y metadata de identidad. | DRIVE-003: acordar explícitamente permiso y alcance global/tenant, revisar todos los consumidores y cambios de tenant. La guarda de UI sola no prueba un contrato backend ni otro hallazgo independiente. |
| Runtime | main crea configuración/DB globales; dotenv relativo, CORS *, pool/timeouts declarados sin consumir y health estático. Compose importa .env global y usa postgres; imagen root con pytest/Ruff en runtime y base sin digest. | DRIVE-002/003/007: factory, modo opcional, readiness y errores saneados, configuración explícita, rol mínimo y contenedor acotado/auditado. La publicación Compose es loopback; no se presupone exposición a Internet. |

El repositorio usa parámetros SQL, filtros propios de conexión/importación y comprobación del padre antes de listar archivos. Las asociaciones conservan propiedad y locks Library. No se encontró un camino probado de SQL injection, SSRF a hosts arbitrarios, ejecución por filename o secreto real incrustado. Las bases remotas son configuración del operador y HTTPX no habilita redirects. `str(exc)` y el texto parcial de errores de upload requieren saneamiento, sin afirmar filtración de credenciales demostrada.

### Decisiones y orden de trabajo

Mantendremos la estructura del servicio y corregiremos sus fronteras con pruebas. Una cola no arreglaría por sí sola identidad, callback ni cifrado; se reconsiderará si los requisitos o las mediciones exigen reanudación/capacidad adicional. No se sostendrán locks de identidad o carpeta durante llamadas Google lentas. No se migrarán ni eliminarán tokens, propietarios, documentos o historial sin un inventario y una estrategia revisados.

Los cuatro paquetes propuestos son runtime/identidad/rol (DRIVE-002/003), OAuth/cifrado y callbacks (DRIVE-004), importaciones y web (DRIVE-005/006), y artefacto/cierre (DRIVE-007/008). Son propuestas para reducir PRs; cada criterio sigue siendo obligatorio y el tamaño puede exigir separar un paquete. Google Drive seguirá opcional y las pruebas usarán transportes/proveedores simulados por defecto.

### Evidencia y límites

En Docker Linux/Python 3.12.16 se ejecutaron las nueve pruebas existentes, Ruff, `pip check`, OpenAPI (siete paths/ocho operaciones) y Compose config. Proyecto dedicado con DB nueva; sin arrancar la integración Google ni montar documentos. Los conteos posteriores de documentos, carpetas, asociaciones, conexiones e importaciones fueron cero. El inventario de dependencias instalado y su auditoría separada se registran en BASELINE; no es un escaneo SO ni una prueba de explotabilidad. Las herramientas de auditoría se instalaron después de congelar el inventario, en un contenedor efímero sin credenciales.

La auditoría no está limpia: OSV devolvió 83 registros, 43 IDs de aviso distintos y siete paquetes; son registros con duplicados, no 83 vulnerabilidades únicas. PyPI devolvió 12 registros/10 IDs atribuidos a un solo paquete, incluyendo avisos que la fuente de Starlette identifica como propios de Starlette. Se conservan ambos resultados sin corregirlos silenciosamente; DRIVE-002 debe verificar atribución y actualizar un conjunto compatible, y DRIVE-007 auditar su imagen final. Se contrastaron el [aviso upstream de cryptography](https://github.com/pyca/cryptography/security/advisories/GHSA-p423-j2cm-9vmq) y los [avisos upstream de Starlette](https://github.com/Kludex/starlette/security/advisories). Ningún conteo prueba por sí solo que una ruta de este servicio sea explotable.

La guía agents-first se contrastó con el [README del framework](https://github.com/Blandskron/agents-first-repo-docs/blob/main/README.md), versión declarada 3.2.0, consultado el 8 de noviembre: entrada humana en README, instrucciones locales en AGENTS, tareas en ROADMAP y evidencia machine-readable sin duplicar código en docs. El portal no estuvo accesible en la consulta; se leyó su fuente conectada en GitHub.

Google exige cotejar state antes de procesar la respuesta; la [guía OAuth web](https://developers.google.com/identity/protocols/oauth2/web-server) y [buenas prácticas](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) respaldan esa frontera y el tratamiento de tokens. La [BCP OAuth RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) orienta PKCE/CSRF y el enlace al navegador; no asumimos compatibilidad de un SDK sin verificar el flujo concreto. La [guía de descarga/exportación Drive](https://developers.google.com/workspace/drive/api/guides/manage-downloads) distingue blobs y exports: su límite de exportación no reemplaza la cota local de la aplicación.
