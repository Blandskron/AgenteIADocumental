# DocumentTransferServices

Registra el historial personal de cargas y descargas mediante FastAPI, SQLAlchemy y PostgreSQL. No recibe archivos, no los descarga ni procesa documentos. Los clientes informan nombres, estados y progreso; este historial no prueba que un navegador haya guardado un archivo ni sustituye la auditoría de DocumentAccessServices. El puerto local de Compose es `8007`.

TRANSFER-001 establece el diagnóstico histórico de la base. TRANSFER-002 incorpora configuración aislada, disponibilidad y pruebas permanentes; TRANSFER-003 establece identidad canónica y referencias autorizadas. TRANSFER-004 corrige metadatos, nulos y límites de entradas. TRANSFER-005 define estados, progreso y limpieza serializada. TRANSFER-006 añade páginas y separa el diario de la operación documental. Ejecución restringida y cierre conservan sus tarjetas. Las correcciones avanzan por incrementos en el [tablero](../../ROADMAP.md#documenttransferservices); [AGENTS.md](AGENTS.md) indica cómo intervenir. Este documento distingue comportamiento observado, decisiones propuestas y comprobaciones pendientes.

## Recorrido y responsabilidades

```text
DocumentSearchPage / ChatPage → useTransfers → transfers.api.js
  → rutas → ManageTransfers → TransferRepositoryPg → transfer_events
```

Solo este servicio escribe directamente `transfer_events` en el backend revisado. El frontend informa eventos desde la carga documental y la descarga; `useDocumentQuestionFlow` también envía el ID de conversación. Google Drive importa por otro flujo y no registra aquí una transferencia explícita. No se debe presentar el historial como un inventario completo de toda operación del sistema.

La tabla contiene propietario, referencia documental opcional, nombre, dirección, estado, progreso, tamaño, JSON y fechas. PostgreSQL exige direcciones UPLOAD/DOWNLOAD, estados conocidos y progreso entre 0 y 100. El índice existente es `(owner_user_id, created_at DESC)` y un trigger actualiza `updated_at`.

Aunque el modelo ORM omite `ForeignKey`, el [esquema compartido](../../scripts/database/schemas/001_documents.sql) sí contiene la referencia a `documents`, con `ON DELETE SET NULL`. Borrar un documento conserva el evento y su nombre. Borrar eventos no elimina documentos ni archivos. No se encontró caducidad automática: la limpieza actual es manual y solo considera estados terminales.

## Contrato HTTP vigente

Todas las rutas de negocio exigen firma RS256, `token_type: access`, `user_id` entero positivo y `exp` entero vigente. Se rechazan booleanos, cadenas, floats, claims ausentes y tokens refresh con 401 y WWW-Authenticate: Bearer. No se resuelve identidad por sub, username o unknown. El propietario del evento siempre es el user_id canónico, aunque el cliente envíe otro o el JWT incluya roles de administración.

| Método y ruta bajo `/api/v1` | Comportamiento actual |
| --- | --- |
| `GET /health` | Público; devuelve `{"status":"ok"}` como comprobación de vida. |
| `GET /health/db` | Público; valida una clave pública RSA legible y consulta las proyecciones requeridas de `transfer_events`, `documents` y `document_assignments` con LIMIT 0, sin leer filas. Clave o PostgreSQL no disponibles devuelven 503 genérico. No audita restricciones, índices ni el esquema de otros servicios. |
| `GET /transfers?limit=50&offset=0` | Página privada con items, limit, offset y has_more; limit de 1 a 200 y offset de 0 a 10000. Orden por created_at e ID descendentes, consultando una fila extra. |
| `POST /transfers` | Crea un evento del propietario canónico; una referencia documental exige acceso vigente. Responde HTTP 200. |
| `PATCH /transfers/{transfer_id}` | Actualiza solo campos enviados de un evento propio. document_id y size_bytes admiten null para retirarlos; una referencia no nula revalida acceso. Evento ajeno o inexistente: 404. |
| `DELETE /transfers/history` | Devuelve `{"count":N}` con las filas realmente borradas: hasta 1000 terminales propios por petición, empezando por los más antiguos. Conserva PENDING y RUNNING; repetir hasta count=0 vacía los terminales disponibles. |

Son cuatro operaciones de negocio y dos healthchecks. La respuesta incluye `transfer_id`, `owner_user_id`, `document_id`, `filename`, `direction`, `status`, `progress`, `size_bytes`, `metadata`, `created_at` y `updated_at`. Las rutas no devuelven rutas de almacenamiento ni contenido documental.

Crear recibe nombre, dirección, estado opcional (PENDING por defecto), progreso (0 por defecto), referencia documental, tamaño y metadatos. Actualizar admite estado, progreso, referencia, tamaño y metadatos. Los modelos rechazan campos extra. `metadata` HTTP se mapea explícitamente a `metadata_` ORM y persiste en la columna JSONB; no se asigna el atributo reservado metadata de SQLAlchemy. Los límites y campos nulos se describen abajo.

## Consumidores que deben cambiar juntos

- El [adaptador](../../frontend/src/features/transfers/api/transfers.api.js) valida páginas explícitas, normaliza sus elementos y codifica IDs. Contratos antiguos o incompletos fallan de forma visible; no se convierten en listas vacías.
- El [hook](../../frontend/src/features/transfers/hooks/useTransfers.js) conecta un controlador por cliente API a React mediante useSyncExternalStore. Refrescar, desmontar o reiniciar invalida respuestas anteriores. Más páginas conservan registros cargados ante fallos; limpiar conserva activos en caché incluso si falla la recarga.
- [TransferModal](../../frontend/src/shared/components/TransferModal/TransferModal.jsx) recorre todos los registros cargados mediante scroll, permite actualizar/cargar más y muestra el conteo cargado. Marca RUNNING, distingue tamaño cero y explica limpieza de terminales por lote.
- [DocumentSearchPage](../../frontend/src/pages/DocumentSearchPage/DocumentSearchPage.jsx) usa los flujos compartidos de carga/descarga. El archivo avanza sin esperar al historial; fallos del diario se anuncian fuera del modal y no repiten el archivo ni reemplazan su error original.
- [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) usa el mismo hook y modal. [useDocumentQuestionFlow](../../frontend/src/features/chat/hooks/useDocumentQuestionFlow.js) espera las escrituras del historial durante la carga y envía `conversation_id` y errores como metadatos.

Los porcentajes 15, 40 y 65 son indicadores de etapas definidos por el cliente, no mediciones de bytes transferidos. Los consumidores ahora omiten progress al guardar FAILED, para conservar la última etapa aceptada por el servidor, y no vuelven a adjuntar un document_id que podría haber sido revocado. La cola del diario se mantiene independiente del resultado documental en TRANSFER-006.

## Diagnóstico histórico TRANSFER-001

Esta tabla describe la imagen anterior a TRANSFER-002 a 005; configuración, disponibilidad, identidad, referencias, metadatos, límites, estados y limpieza ya se corrigieron como se explica abajo. Las demás brechas conservan sus incrementos pendientes. Se revisaron todos los módulos del servicio, las seis rutas, el esquema, restricciones, índice, trigger, Compose, workflow de CI y los consumidores anteriores. La sonda temporal confirmó 25 observaciones sobre PostgreSQL con datos sintéticos y transacción externa/savepoints; también confirmó su rollback final. No cargó archivos, llamó a IA ni utilizó OAuth o claves reales.

| Área | Evidencia y efecto | Incremento |
| --- | --- | --- |
| Identidad | Un access token firmado sin exp y otro con user_id booleano fueron aceptados. Dos conjuntos distintos de claims sin identidad operaron sobre el mismo propietario `unknown`. | TRANSFER-003 |
| Propiedad personal | Con identidades canónicas distintas, el listado filtra por propietario y PATCH ajeno devuelve 404. Mantener esa privacidad sin privilegios globales de administradores. | TRANSFER-003 |
| Referencia documental | Se aceptó un ID documental ajeno; el servicio no consulta permisos documentales. Un ID inexistente produjo 500 por la FK. No se observó lectura de su contenido: la incoherencia es del vínculo del historial. | TRANSFER-003 |
| Metadatos y nulos | Crear y actualizar JSON no vacío no lo persistió. Enviar document_id null no retiró el vínculo. | TRANSFER-004 |
| Entradas y errores | Se aceptaron nombre de espacios y tamaño negativo. Un entero fuera de BIGINT produjo 500. Un error 422 reflejó el valor enviado. | TRANSFER-004 |
| Estados | Se aceptó COMPLETED con progreso 1 y se reabrió un COMPLETED como RUNNING con progreso 0. No hay exclusión entre actualizaciones ni política de reintentos. | TRANSFER-005 |
| Limpieza y retención | La limpieza SQL conservó RUNNING; la interfaz elimina también esos registros de su caché. El borrado actual materializa todas las filas terminales; las carreras requieren pruebas independientes. | TRANSFER-005 / TRANSFER-006 |
| Configuración | CORS autoriza `*`; Compose inyecta el entorno global y usa postgres. Settings acepta cotas negativas de pool; el motor retiene tamaño 5 pese al mínimo declarado 1 y no aplica las opciones publicadas. | TRANSFER-002 / TRANSFER-007 |
| Disponibilidad | health/db devolvió 200 con una ruta de clave inexistente. Una excepción en lifespan omite database.close. | TRANSFER-002 |
| Ejecución y mantenimiento | Imagen UID 0, con pytest y Ruff. Sin suite propia ni etapa de tests en CI. Entidad, tipo vectorial, constantes de extracción y utilidades sin consumidores internos encontrados. | TRANSFER-002 / TRANSFER-007 / TRANSFER-008 |
| Dependencias | pip check y Ruff aprobaron, pero la auditoría detectó avisos en seis paquetes. No confundir resolución de dependencias o lint con seguridad de la imagen. | TRANSFER-007 |

La línea base del 6 de noviembre de 2026 construyó el manifiesto `sha256:f6c7ec04a4696251eef382a621cdfc90cbd2009f334461a2cd404a9acbdc1c67` sin cambiar el servicio. En un contenedor desechable se congelaron 33 paquetes antes de instalar las herramientas de la sonda. `pip-audit` 2.10.1 informó 58 entradas en `cryptography 46.0.6`, `pip 25.0.1`, `PyJWT 2.12.1`, `pytest 8.3.5`, `python-dotenv 1.1.0` y `starlette 0.46.2`. Las entradas pueden incluir aliases o duplicaciones; no representan 58 vulnerabilidades únicas validadas. El sistema operativo de esta imagen no se escaneó en TRANSFER-001; se hará al actualizar la imagen.

La evidencia combina inspección estática y sondas. No constituye una auditoría exhaustiva ni afirma explotación de los avisos de dependencias. Las pruebas permanentes de configuración, identidad, referencias y su carrera con borrado ya se incorporaron; la concurrencia de estados y limpieza se incorporó en TRANSFER-005, sin convertir la base defectuosa en el comportamiento esperado a conservar.

## Decisiones para los incrementos

1. Mantener el historial privado por user_id canónico. Un evento no concede lectura documental y no es una prueba de entrega de archivos. No agregar tenant ni una vista administrativa global sin una decisión explícita.
2. Validar vínculos según los permisos documentales vigentes y responder de forma indistinguible ante IDs ajenos o inexistentes. Conservar eventos después de borrar documentos y no reasignar registros `unknown` a un usuario sin evidencia de propiedad.
3. Definir campos ausentes frente a nulos, persistir JSON correctamente y acotar datos antes de escribir. Auditar datos existentes antes de imponer nuevas restricciones; no corregirlos mediante borrados silenciosos.
4. Definir transiciones y reintentos coherentes con los indicadores de etapas del cliente. Probar concurrencia y rollback entre sesiones antes de declarar consistencia.
5. Separar el resultado documental del resultado del historial. Un fallo al registrar no debe provocar otra carga/descarga automática ni presentar como perdido un documento ya creado; las advertencias deben seguir visibles.
6. Paginar con orden estable, conservar activos al limpiar y descartar respuestas de clientes anteriores. Adaptar ambos recorridos web, hook, adaptador y modal en el mismo incremento.
7. Terminar con rol mínimo, imagen sin root, auditoría y README operativo. Mantener contexto breve en AGENTS y las tareas en ROADMAP, siguiendo los principios de leer primero y aportar evidencia de la [guía agents-first compartida](https://github.com/Blandskron/agents-first-repo-docs/blob/main/README.md) (v3.2.0, revisada el 6 de noviembre de 2026).

## Identidad, referencias e historial personal (TRANSFER-003)

El listado, PATCH y limpieza filtran siempre por el propietario del evento. Ser superadmin o administrador de tenant no permite consultar ni modificar el historial de otra persona. Los nombres y metadatos ya registrados permanecen en el historial personal después de revocar un permiso documental; no conceden lectura, descarga ni otro permiso sobre el documento.

Crear con document_id o enviar document_id no nulo en PATCH exige lectura vigente según la política compartida por Library y Access:

- Propietario: columna owner_user_id; solo si es SQL NULL se usa metadata.owner_user_id. Una columna vacía o diferente no se sustituye por metadatos.
- Asignación como destinatario o remitente, con estado distinto de CANCELLED/EXPIRED.
- Administrador del tenant resuelto: columna tenant_id y fallback de metadatos únicamente si es NULL.
- Grupo documental presente en el JWT, limitado a los tenants de membresía o a un documento sin tenant.
- Superadmin puede referenciar documentos globalmente, conservando su historial privado.

El servicio no exige PROCESSED, embeddings ni allow_download para registrar una referencia: este historial no ejecuta ni autoriza descargas. El resultado de la operación documental corresponde a su servicio. Un documento ajeno o inexistente devuelve el mismo 404 `Document not found.`. En PATCH se comprueba primero la propiedad del evento; un evento ajeno o inexistente devuelve 404 `Transfer not found.` sin revelar sus referencias.

Cada vínculo enviado se revalida, incluso si coincide con el anterior. Omitir document_id permite actualizar el diario propio tras una revocación; enviar document_id: null retira la referencia, sin leer el documento ni borrar su historial. Se usa FOR KEY SHARE durante la transacción para impedir que un borrado entre la comprobación y la escritura produzca una FK inválida. Si borra primero, el vínculo responde 404; si vincula primero, el borrado espera y SET NULL conserva el evento. Las excepciones de alta/actualización revierten la sesión. No se afirma serialización total frente a cambios simultáneos de permisos: la política consulta el estado visible en la comprobación, y el JWT mantiene los claims emitidos hasta su renovación/expiración, como los demás servicios. TRANSFER-005 define las reglas de estados y las carreras de limpieza.

La imagen actual usa postgres. FOR KEY SHARE requiere privilegios de bloqueo; TRANSFER-007 deberá sustituirlo por una capacidad acotada al introducir el rol mínimo, manteniendo las pruebas concurrentes y sin conceder UPDATE documental genérico al runtime.

### Auditoría de propietarios históricos

Antes de actualizar una instalación con historial, ejecuta la auditoría agregada de solo lectura desde PowerShell:

```powershell
Get-Content scripts/database/transfer/audit_owners.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
```

En bash se puede usar la misma llamada psql con `< scripts/database/transfer/audit_owners.sql`. El script ejecuta BEGIN READ ONLY y devuelve categorías/conteos, sin imprimir identificadores ni modificar filas. Distingue unknown, números con formato canónico, números no canónicos y otros valores. Un número canónico **no acredita** propiedad histórica: podría provenir de un antiguo sub o username numérico. Los registros ambiguos se preservan; no se reasignan por similitud ni se borran. Investigar su procedencia y cualquier reparación requiere respaldo, evidencia de propiedad y decisión explícita. Los propietarios no canónicos no son alcanzables mediante la nueva identidad canónica.

La ejecución local sobre la base de desarrollo revisada encontró cero eventos; no representa una auditoría de otras instalaciones. Las pruebas verifican las cuatro categorías con datos sintéticos y que el SELECT conserva los valores originales. CI ejecuta también el script completo.

Evidencia TRANSFER-003: 155 pruebas aprobadas, Ruff, Compose, pip check y arranque real. Las matrices HTTP cubren claims inválidos en las cuatro operaciones, firmas/algoritmos incorrectos, precedencia de identidad, privacidad incluso para administradores, propietarios históricos, permisos por dueño/asignación/tenant/grupo, precedencia de columnas sobre JSON, revocación, 404 indistinguible, preservación documental e historial. Cuatro casos concurrentes con sesiones independientes observan pg_stat_activity.wait_event_type=Lock y comprueban ambos órdenes de alta/PATCH frente al borrado, recuperación y limpieza por IDs sintéticos. La suite usa claves temporales; una comprobación adicional contra el contenedor real aceptó access tokens emitidos y renovados por Auth y rechazó refresh, con rollback del usuario sintético y sin escribir historial.

## Entradas, metadatos y errores (TRANSFER-004)

| Campo o límite | Contrato de entrada |
| --- | --- |
| filename | Texto de 1 a 512 caracteres Unicode válidos. Conserva espacios de los extremos; rechaza nombres compuestos solo de espacios y controles C0/DEL. Es una etiqueta, nunca una ruta para abrir archivos. |
| document_id y transfer_id de PATCH | Texto de 1 a 128 caracteres, no vacío/blanco, sin controles ni Unicode inválido. No exige UUID para conservar IDs históricos válidos. |
| progress | Entero estricto de 0 a 100. No convierte cadenas, booleanos ni floats. TRANSFER-005 exige monotonía y congela progreso terminal. |
| size_bytes | Entero estricto de 0 a 9223372036854775807, compatible con BIGINT; cero es un tamaño conocido. null representa tamaño desconocido. |
| metadata | Objeto JSON de hasta 16384 bytes UTF-8 en serialización compacta sin escapes ASCII. Máximo 16 niveles desde la raíz (raíz en 0; claves/valores/elementos incrementan nivel). Rechaza NaN/Infinity, NUL en claves o valores y Unicode inválido. |
| Cuerpo HTTP | Hasta 65536 bytes reales, incluidos espacios y fragmentos, con o sin Content-Length; excederlos devuelve 413 antes del parseo y de la ruta. No es un timeout de lectura ni un control de tasa. |
| Campos desconocidos | 422, incluidos owner_user_id, metadata_ o campos inmutables enviados en PATCH. |

En PATCH, omitir un campo lo conserva. document_id: null y size_bytes: null retiran sus valores; metadata: {} vacía el JSON. metadata reemplaza el objeto completo, no lo mezcla. status, progress y metadata explícitamente nulos se rechazan; un PATCH vacío también devuelve 422. Crear admite document_id/size_bytes nulos, pero metadata requiere objeto. No se crean metadatos históricos a partir de datos que no llegaron a persistir.

La respuesta conserva su forma, nombres y códigos de éxito. Los 422 contienen ubicación normalizada, tipo de error y mensaje genérico, sin input, contexto, valores ni claves arbitrarias enviados. SQLAlchemy devuelve 500 `Database operation failed.` y AppError interno devuelve 500 genérico; las escrituras de alta, PATCH y limpieza revierten la sesión tras errores. Las validaciones de dominio mantienen 400 y referencias/eventos inexistentes o ajenos mantienen 404. JSON malformado o excesivamente profundo devuelve 400/422 privado según la fase de parseo/validación. Una respuesta de error no refleja el documento ni las credenciales de conexión.

Se revisaron transfers.api.js, useTransfers, TransferModal, DocumentSearchPage y useDocumentQuestionFlow. Los payloads actuales usan campos admitidos y objetos JSON: conversation_id puede ser null dentro de metadata y los errores de operación se conservan dentro del límite. El adaptador preserva estos datos, tamaño cero y nulos explícitos; no requiere cambiar su código para este incremento. Las pruebas de contrato web verifican esa compatibilidad y la propagación del error original del cliente HTTP. TRANSFER-006 separa las operaciones y descarta respuestas tardías; un error o nombre superior al límite se rechaza, no se trunca silenciosamente.

Evidencia TRANSFER-004: 230 pruebas backend con PostgreSQL y 32 frontend, Ruff, npm ci/test/build, pip check, Compose y arranque real aprobados. Round trip JSONB de alta/PATCH/listado, reemplazo y vaciado; ausencia frente a null; fronteras de Unicode, IDs, BIGINT, profundidad/bytes JSON, números no finitos, cuerpo completo/fragmentado y cabeceras engañosas; rechazo sin escrituras, privacidad y recuperación cubiertos. Fallos SQL reales en INSERT/UPDATE/DELETE se inyectan únicamente en una tabla y función temporales de una conexión, sin modificar tablas compartidas; después del 500 la misma sesión puede operar. Datos sintéticos con rollback verificado. No cambia el esquema ni corrige datos históricos. Persisten el aviso de deprecación Starlette/AnyIO y cuatro alertas altas de npm, en sus seguimientos.

## Estados, progreso y limpieza (TRANSFER-005)

| Estado actual | Estados siguientes admitidos |
| --- | --- |
| PENDING | PENDING, RUNNING, COMPLETED, FAILED, CANCELLED |
| RUNNING | RUNNING, COMPLETED, FAILED, CANCELLED |
| COMPLETED / FAILED / CANCELLED | Solo el mismo estado; no se reabre un terminal. Una nueva operación crea otro evento. |

El progreso representa etapas informadas por el cliente, no bytes medidos. Es independiente de PENDING/RUNNING y puede ir de 0 a 100 en ambos; 100 por sí solo no termina una operación. Nunca disminuye. Al pasar a terminal queda congelado; FAILED/CANCELLED conservan la última etapa si se omite progress. COMPLETED exige progress=100: crear otra combinación devuelve 400 y un PATCH incompatible devuelve 409, sin escrituras parciales. El servidor no infiere el resultado documental ni completa porcentajes omitidos.

Un PATCH idéntico puede repetirse y no emite otro UPDATE ni altera fechas; enviar una referencia sigue revalidando su permiso. Se permiten correcciones de metadatos, tamaño y referencia en un terminal sin reabrirlo. Los registros históricos incoherentes no se reparan automáticamente: pueden conservarse o limpiarse; corregir su estado/progreso histórico requiere una decisión y reparación explícitas. POST crea un evento nuevo cada vez: no deduplica por nombre ni debe reintentarse automáticamente después de perder una respuesta.

Todas las escrituras del servicio toman un advisory lock transaccional por propietario. Las solicitudes de la misma persona se ordenan; otras personas no comparten ese bloqueo. PATCH vuelve a leer la fila con FOR UPDATE y populate_existing, evitando validar una versión obsoleta. Al adjuntar un documento el orden es propietario → documento (KEY SHARE) → evento, compatible con el borrado documental y su SET NULL. No se bloquea el documento al corregir solo el diario o al retirar la referencia.

Alta y PATCH hacen flush/refresh y separan la respuesta del ORM mientras conservan sus bloqueos; después confirman. Así, una limpieza posterior puede retirar la fila sin provocar un refresh o una carga diferida fallida en la respuesta anterior. Un fallo de confirmación devuelve error y revierte la operación; no se devuelve una instantánea de éxito si falló commit. El protocolo coordina escritores de este servicio; no impone estas reglas a escrituras SQL externas ni crea restricciones nuevas en el esquema compartido. El rol mínimo y la capacidad de bloqueo siguen en TRANSFER-007.

DELETE history ejecuta un único DELETE SQL con subconsulta limitada a 1000 terminales propios, ordenados por created_at e ID. No carga sus objetos en Python ni borra documentos, archivos o eventos ajenos. Devuelve el contador efectivo; otra limpieza serializada no cuenta dos veces las mismas filas. Activos, altas posteriores y terminales fuera del lote permanecen. La interfaz informa el límite, refresca la primera página y permite repetir la acción. TRANSFER-006 incorpora páginas, descarta respuestas tardías y presenta errores sin vaciar silenciosamente un contrato inválido.

DocumentSearchPage y useDocumentQuestionFlow usan un constructor común de fallo que envía FAILED y metadata.error/conversation_id, sin progreso inicial obsoleto ni una referencia documental repetida. La interfaz conserva la advertencia de que se limpian solo terminales. TRANSFER-006 completa la separación entre el resultado del archivo y el diario, con advertencia visible ante un fallo tardío.

Evidencia: 280 pruebas backend PostgreSQL y 34 frontend, Ruff, npm ci/test/build, pip check, Compose y arranque sobre volumen existente. La matriz de 25 transiciones, monotonía, terminales, completion=100, reintentos sin UPDATE y lotes 1000/1/0 se verifica por HTTP y SQL. Sesiones independientes observan esperas Lock para avances concurrentes, conflictos terminales, PATCH/alta frente a limpieza, dos limpiezas, rollback frente a limpieza y ambos órdenes de PATCH/limpieza frente al borrado documental. Se comprueban independencia entre propietarios, snapshots utilizables tras borrado, SET NULL, ausencia de conteos dobles, rollback y recuperación. Los fixtures compartidos limpian datos sintéticos; ninguna prueba usa IA u OAuth. Persisten las cuatro alertas altas npm y la deprecación Starlette/AnyIO registradas.

## Páginas y operaciones independientes (TRANSFER-006)

GET transfers devuelve `{items, limit, offset, has_more}`. La web solicita 50 registros y puede cargar las páginas siguientes; el contador representa filas cargadas, no un total global. La API admite hasta 200 por página y offset hasta 10000, con 422 privado fuera de rango. El orden usa created_at e ID para resolver empates. La deduplicación web no altera el avance del offset, calculado con el tamaño bruto de la página.

Offset no crea una instantánea entre peticiones: altas o limpiezas externas pueden mover las posiciones y requerir Actualizar historial. El cliente vuelve a la primera página después de sus propias escrituras para no conservar offsets incoherentes. Actualizar descarta la ventana anterior; un fallo al cargar más conserva los registros anteriores y permite reintentar. Al alcanzar la cota de offset, la API devuelve 422; refresca o limpia terminales para reducir la ventana. No se afirma recorrido ilimitado ni consistencia de instantánea ante cambios externos.

Cada cliente tiene un controlador independiente con generaciones para peticiones y ciclo de vida. Descarta listas, escrituras, limpiezas y advertencias tardías de un cliente desmontado o de una generación previa, incluido el reinicio de efectos de React. Un clic repetido de paginación o limpieza no duplica esa solicitud. Los errores de listado/limpieza se muestran en el modal. Tras una limpieza correcta, la caché conserva los activos incluso si falla la consulta posterior; los terminales restantes se vuelven a consultar.

Los flujos compartidos de carga, carga desde Chat y descarga inician la operación documental una vez, sin esperar la creación del diario. Sus actualizaciones se encadenan en una cola de alta → etapa 65 (si corresponde) → terminal, independiente de la respuesta documental. Un fallo, retraso o petición pendiente del diario no impide obtener el archivo/documento ni cambia su resultado. Si falla la operación documental, se propaga exactamente su error original; fallar al registrar FAILED no lo sustituye. No hay reintento automático de archivos ni de POST del historial.

Las advertencias del historial se conservan aunque se refresque el listado y aparecen como estado visible fuera del modal en Search y Chat; pueden cerrarse explícitamente. Un cliente retirado no inicia pasos pendientes del diario ni publica avisos en el siguiente. Una petición ya enviada puede completar en el servidor: descartar su respuesta no revierte ese commit. Tampoco se promete entrega duradera del diario si se cierra la pestaña antes de completar la cola; este historial continúa siendo información del cliente, no prueba de entrega ni auditoría autoritativa.

El modal muestra todos los registros cargados mediante scroll, controles Actualizar/Cargar más y tamaños de cero bytes. Backend y frontend deben desplegarse juntos: el adaptador rechaza arreglos antiguos, offsets/limit incorrectos o filas sin ID en vez de ocultarlos con una lista vacía. Las respuestas de alta/PATCH y el lote de limpieza no cambian.

Evidencia: 288 pruebas PostgreSQL/HTTP y 60 frontend, Ruff, npm ci/test/build, pip check, Compose y arranque saludable aprobados. La suite backend recorre 207 eventos privados con fechas empatadas, páginas 100/100/7, final vacío y cotas de offset. Web prueba carga incremental, deduplicación/avance bruto, clics repetidos, errores, refresh/reinicio/disposición, respuestas tardías y limpieza con recarga fallida. Los tres flujos se prueban con alta fallida, PATCH fallido, alta pendiente, error documental original y etapas ordenadas después de alta lenta; ninguna operación documental se repite. El render SSR del componente verifica doce filas, tamaño cero, controles y aviso accesible fuera del modal; no equivale a un recorrido visual completo de navegador ni a auditoría de accesibilidad. No se usan IA/OAuth ni archivos reales. Persisten los seguimientos npm e imagen/dependencias.

## Configuración y operación (TRANSFER-002)

Compose transmite solo diez variables: APP_ENV, APP_NAME, LOG_LEVEL, CORS_ORIGINS, DATABASE_URL, AUTH_JWT_PUBLIC_KEY_PATH, AUTH_JWT_ALGORITHM y las tres opciones DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE, DB_TIMEOUT_SECONDS. El servicio no carga archivos .env automáticamente. Compose usa el archivo raíz para interpolar opciones explícitas; no lo inyecta completo. Transfer no necesita claves de Groq, OAuth ni la clave privada de Auth.

CORS permite por defecto http://localhost:3000 y http://127.0.0.1:3000, sin credenciales de navegador. Puede configurarse con TRANSFER_CORS_ORIGINS como arreglo JSON. RS256 es el único algoritmo configurable admitido. Se monta únicamente el volumen público de Auth, de solo lectura.

| Variable de Compose | Predeterminado | Semántica |
| --- | --- | --- |
| TRANSFER_DB_POOL_MIN_SIZE | 1 | Conexiones retenidas por el pool, creadas bajo demanda, de 1 a 100; no es un precalentamiento mínimo. |
| TRANSFER_DB_POOL_MAX_SIZE | 10 | Capacidad total, de 1 a 100 y al menos el tamaño retenido; el excedente se descarta al liberarse. |
| TRANSFER_DB_TIMEOUT_SECONDS | 30 | De 1 a 300 segundos; espera del pool y connect_timeout de PostgreSQL. No limita la duración de cada consulta SQL. |

La configuración inválida detiene la aplicación antes del arranque. El pool usa pre_ping; las sesiones cierran y revierten trabajo no confirmado al salir, incluso ante excepciones. El lifespan libera el motor mediante finally y puede volver a abrirlo en otro arranque. Liveness no requiere dependencias; readiness no usa la caché de claves JWT y detecta cambios en el archivo en cada llamada.

Prepara `.env` siguiendo el [README principal](../../README.md). Desde la raíz:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-transfer-service
curl http://localhost:8007/api/v1/health
curl http://localhost:8007/api/v1/health/db

docker compose -f docker/docker-compose.yml exec -T document-transfer-service python -m pip --no-cache-dir check
docker compose -f docker/docker-compose.yml run --build --rm --no-deps transfer-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps transfer-tests ruff check --no-cache app tests
```

La etapa Docker test instala requirements-test.txt; la imagen runtime no contiene pytest, Ruff ni httpx. El job auth-db-roles de CI arranca Transfer y ejecuta la suite y Ruff; el job compose comprueba las diez variables y readiness. El job ejecuta también la auditoría agregada de propietarios. La suite requiere TRANSFER_TEST_DATABASE_URL explícita para operaciones sintéticas y DATABASE_URL para el motor de la aplicación; Compose configura ambas contra PostgreSQL local. No ejecutar contra producción. No usa create_all ni migra tablas compartidas.

Evidencia local de TRANSFER-002: 46 pruebas aprobadas con PostgreSQL y claves RSA temporales; Ruff, pip check, Compose y arranque real con clave pública montada aprobados. Se verificaron límites de settings, precedencia del entorno sin carga de .env, capacidad/timeout/recuperación del pool, rollback tras error SQL, cierre normal/interrumpido/fallo de arranque, reapertura, CORS, 401 en cuatro operaciones, clave ausente/malformada/no RSA y su recuperación, cada columna requerida, conexión caída con 503 privado y recorrido crear/listar/actualizar/limpiar con rollback verificado. Las alteraciones de esquema se limitan a tablas temporales de una conexión, sin cambiar las compartidas.

El arranque local se verificó sobre dependencias de desarrollo existentes, sin publicar puertos adicionales; CI comprueba el arranque desde su entorno desechable. No se ejecutó el stack completo ni una prueba con proveedor IA. Starlette emite un aviso de deprecación de BlockingPortal con AnyIO; la actualización y auditoría de dependencias corresponde a TRANSFER-007. La imagen aún ejecuta como root y usa postgres: rol mínimo, auditoría y ejecución restringida permanecen pendientes. TRANSFER-006 amplía la suite a 288 pruebas backend y 60 frontend; ejecución restringida, auditoría y cierre operativo permanecen pendientes.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
