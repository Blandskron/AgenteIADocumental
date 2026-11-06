# DocumentTransferServices

Registra el historial personal de cargas y descargas mediante FastAPI, SQLAlchemy y PostgreSQL. No recibe archivos, no los descarga ni procesa documentos. Los clientes informan nombres, estados y progreso; este historial no prueba que un navegador haya guardado un archivo ni sustituye la auditoría de DocumentAccessServices. El puerto local de Compose es `8007`.

TRANSFER-001 establece el diagnóstico de la base actual. Las correcciones avanzan por incrementos en el [tablero](../../ROADMAP.md#documenttransferservices); [AGENTS.md](AGENTS.md) indica cómo intervenir. Este documento distingue comportamiento observado, decisiones propuestas y comprobaciones pendientes.

## Recorrido y responsabilidades

```text
DocumentSearchPage / ChatPage → useTransfers → transfers.api.js
  → rutas → ManageTransfers → TransferRepositoryPg → transfer_events
```

Solo este servicio escribe directamente `transfer_events` en el backend revisado. El frontend informa eventos desde la carga documental y la descarga; `useDocumentQuestionFlow` también envía el ID de conversación. Google Drive importa por otro flujo y no registra aquí una transferencia explícita. No se debe presentar el historial como un inventario completo de toda operación del sistema.

La tabla contiene propietario, referencia documental opcional, nombre, dirección, estado, progreso, tamaño, JSON y fechas. PostgreSQL exige direcciones UPLOAD/DOWNLOAD, estados conocidos y progreso entre 0 y 100. El índice existente es `(owner_user_id, created_at DESC)` y un trigger actualiza `updated_at`.

Aunque el modelo ORM omite `ForeignKey`, el [esquema compartido](../../scripts/database/schemas/001_documents.sql) sí contiene la referencia a `documents`, con `ON DELETE SET NULL`. Borrar un documento conserva el evento y su nombre. Borrar eventos no elimina documentos ni archivos. No se encontró caducidad automática: la limpieza actual es manual y solo considera estados terminales.

## Contrato HTTP de la base

Todas las rutas de negocio verifican firma JWT y `token_type: access`. La base no exige `exp` ni un `user_id` entero positivo; el repositorio usa `user_id`, luego `sub`, luego `username` y finalmente `unknown`. TRANSFER-003 debe sustituir esas alternativas por la identidad canónica antes de considerar cerrado el aislamiento. Los tokens de Auth normales incluyen los claims; la sonda comprueba qué ocurre ante otros claims firmados, sin usar la clave de Auth.

| Método y ruta bajo `/api/v1` | Comportamiento actual |
| --- | --- |
| `GET /health` | Público; devuelve `{"status":"ok"}` como comprobación de vida. |
| `GET /health/db` | Público; consulta un ID de `transfer_events`. No valida la clave pública ni todas las columnas; errores de PostgreSQL no se traducen a 503. |
| `GET /transfers?limit=50` | Arreglo de eventos propios, ordenados por creación descendente; `limit` de 1 a 200. No tiene offset ni desempate por ID. |
| `POST /transfers` | Crea un evento del propietario resuelto; responde HTTP 200. |
| `PATCH /transfers/{transfer_id}` | Cambia campos no nulos de un evento propio. Un ID ajeno o inexistente devuelve 404. |
| `DELETE /transfers/history` | Devuelve `{"count":N}` y elimina eventos propios COMPLETED, FAILED o CANCELLED. Conserva PENDING y RUNNING. Materializa las filas antes de borrarlas. |

Son cuatro operaciones de negocio y dos healthchecks. La respuesta incluye `transfer_id`, `owner_user_id`, `document_id`, `filename`, `direction`, `status`, `progress`, `size_bytes`, `metadata`, `created_at` y `updated_at`. Las rutas no devuelven rutas de almacenamiento ni contenido documental.

Crear recibe nombre, dirección, estado opcional (PENDING por defecto), progreso (0 por defecto), referencia documental, tamaño y metadatos. Actualizar admite estado, progreso, referencia, tamaño y metadatos. Los modelos ignoran campos extra y no limitan longitudes, tamaño JSON o cuerpo HTTP. El nombre solo exige longitud antes de recortar; el tamaño no tiene cota no negativa ni de BIGINT. `model_dump(exclude_none=True)` hace que enviar `document_id: null` no retire una referencia existente.

El campo HTTP `metadata` no se mapea al atributo ORM `metadata_`. En las sondas, crear o actualizar con un objeto no vacío devuelve y conserva `{}` en la columna. TRANSFER-004 debe corregir ese round trip sin escribir sobre el atributo reservado de SQLAlchemy ni inventar datos históricos que no llegaron a guardarse.

## Consumidores que deben cambiar juntos

- El [adaptador](../../frontend/src/features/transfers/api/transfers.api.js) convierte arreglos y transforma cualquier objeto paginado en una lista vacía. Hay que adaptar el contrato junto con backend y sus pruebas.
- El [hook](../../frontend/src/features/transfers/hooks/useTransfers.js) carga cincuenta eventos y acumula altas/actualizaciones locales. No invalida respuestas al cambiar cliente o desmontar. `clearHistory` vacía todo el estado local, aunque el servidor conserve eventos activos; tampoco captura sus errores.
- [TransferModal](../../frontend/src/shared/components/TransferModal/TransferModal.jsx) solo muestra seis eventos. No permite recorrer los restantes y solo destaca el primer RUNNING visible. Trata tamaño cero como desconocido. El botón de limpiar no explica que conserva procesos activos.
- [DocumentSearchPage](../../frontend/src/pages/DocumentSearchPage/DocumentSearchPage.jsx) crea el evento antes de cargar/descargar. Una falla del historial puede impedir iniciar la operación documental o comunicar como fallo una operación ya completada. El intento de guardar FAILED también puede fallar y ocultar el error original.
- [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) usa el mismo hook y modal. [useDocumentQuestionFlow](../../frontend/src/features/chat/hooks/useDocumentQuestionFlow.js) espera las escrituras del historial durante la carga y envía `conversation_id` y errores como metadatos.

Los porcentajes 15, 40 y 65 son indicadores de etapas definidos por el cliente, no mediciones de bytes transferidos. Un fallo usa el progreso del objeto inicial, que puede ser anterior al último progreso enviado. Por eso las reglas de monotonía y estados deben coordinarse con estos consumidores. No basta con bloquear regresiones en SQL sin revisar los flujos de error.

## Diagnóstico TRANSFER-001

Se revisaron todos los módulos del servicio, las seis rutas, el esquema, restricciones, índice, trigger, Compose, workflow de CI y los consumidores anteriores. La sonda temporal confirmó 25 observaciones sobre PostgreSQL con datos sintéticos y transacción externa/savepoints; también confirmó su rollback final. No cargó archivos, llamó a IA ni utilizó OAuth o claves reales.

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

La evidencia combina inspección estática y sondas. No constituye una auditoría exhaustiva ni afirma explotación de los avisos de dependencias. Las pruebas permanentes y comprobaciones concurrentes se incorporarán con las correcciones, sin convertir la base defectuosa en el comportamiento esperado a conservar.

## Decisiones para los incrementos

1. Mantener el historial privado por user_id canónico. Un evento no concede lectura documental y no es una prueba de entrega de archivos. No agregar tenant ni una vista administrativa global sin una decisión explícita.
2. Validar vínculos según los permisos documentales vigentes y responder de forma indistinguible ante IDs ajenos o inexistentes. Conservar eventos después de borrar documentos y no reasignar registros `unknown` a un usuario sin evidencia de propiedad.
3. Definir campos ausentes frente a nulos, persistir JSON correctamente y acotar datos antes de escribir. Auditar datos existentes antes de imponer nuevas restricciones; no corregirlos mediante borrados silenciosos.
4. Definir transiciones y reintentos coherentes con los indicadores de etapas del cliente. Probar concurrencia y rollback entre sesiones antes de declarar consistencia.
5. Separar el resultado documental del resultado del historial. Un fallo al registrar no debe provocar otra carga/descarga automática ni presentar como perdido un documento ya creado; las advertencias deben seguir visibles.
6. Paginar con orden estable, conservar activos al limpiar y descartar respuestas de clientes anteriores. Adaptar ambos recorridos web, hook, adaptador y modal en el mismo incremento.
7. Terminar con rol mínimo, imagen sin root, auditoría y README operativo. Mantener contexto breve en AGENTS y las tareas en ROADMAP, siguiendo los principios de leer primero y aportar evidencia de la [guía agents-first compartida](https://github.com/Blandskron/agents-first-repo-docs/blob/main/README.md) (v3.2.0, revisada el 6 de noviembre de 2026).

## Arranque y comprobaciones de la base

Prepara `.env` siguiendo el [README principal](../../README.md). Los comandos disponibles desde la raíz son:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-transfer-service
curl http://localhost:8007/api/v1/health
curl http://localhost:8007/api/v1/health/db
docker compose -f docker/docker-compose.yml run --rm --no-deps document-transfer-service python -m pip --no-cache-dir check
docker compose -f docker/docker-compose.yml run --rm --no-deps document-transfer-service ruff check --no-cache app
```

Durante TRANSFER-001 se verificaron Compose, construcción de la imagen, pip check, Ruff y la sonda HTTP/SQL aislada descrita arriba. No se levantó el stack completo ni se ejecutó una suite propia inexistente. No se modificaron dependencias, rutas, datos persistentes o configuración del servicio. La siguiente tarjeta incorpora configuración aislada y pruebas reproducibles en CI.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
