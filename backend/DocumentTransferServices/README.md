# DocumentTransferServices

> Evidencia transversal vigente: [verificación de entrega](../../docs/release/README.md) e [imágenes finales](../../docs/release/IMAGE_AUDIT.json). Runtime Python sin pip/ensurepip; comprobación del grafo durante el build, herramientas en test/audit. Los escaneos fechados anteriores conservan su valor histórico y no describen esta imagen.

Historial personal de cargas y descargas de Blandskron Documental. FastAPI registra los eventos que informa el cliente; no recibe archivos, no los descarga ni acredita su recepción. El puerto local es 8007. Google Drive usa otro recorrido y no registra aquí todas sus importaciones.

## Recorrido y archivos de referencia

```text
Search / Chat → flujos documentales + cola independiente del diario
  → useTransfers / controlador por cliente → API → caso de uso → repositorio → PostgreSQL
```

| Responsabilidad | Referencia |
| --- | --- |
| Contratos, límites y rutas | [schemas](app/interfaces/api/v1/schemas/transfer_schema.py), [rutas](app/interfaces/api/v1/routes/transfer_routes.py), [límite de cuerpo](app/interfaces/api/body_limit.py) |
| Estados y transacciones | [dominio](app/domain/transfer_state.py), [caso de uso](app/application/use_cases/manage_transfers.py), [repositorio](app/infrastructure/database/repositories/transfer_repository_pg.py) |
| Configuración y arranque | [settings](app/config/settings.py), [lifespan y errores](app/main.py), [Compose](../../docker/compose/documents.yml) |
| Esquema y rol mínimo | [esquema compartido](../../scripts/database/schemas/001_documents.sql), [permisos](../../scripts/database/transfer/permissions.sql), [verificador](../../scripts/database/transfer/verify_role.sql) |
| Consumidores web | [controlador](../../frontend/src/features/transfers/transfer-controller.js), [flujos](../../frontend/src/features/transfers/document-transfer-flows.js), [hook de Chat](../../frontend/src/features/chat/hooks/useDocumentQuestionFlow.js) |

Consulta [AGENTS.md](AGENTS.md) para colaborar y la [verificación de entrega](../../docs/release/README.md) para evidencia transversal, alcance y avisos.

## Contrato HTTP

Todas las operaciones de negocio exigen firma RS256, token_type access, user_id entero positivo y exp entero vigente. Booleanos, floats, cadenas y claims ausentes se rechazan con 401 y WWW-Authenticate: Bearer. No hay identidad alternativa por sub, username o unknown. El propietario siempre procede del JWT, incluso para administradores.

| Método bajo /api/v1 | Resultado |
| --- | --- |
| GET /health | Vida pública, sin consultar dependencias. |
| GET /health/db | Clave pública RSA legible, proyecciones necesarias de tres tablas con LIMIT 0 y función de referencia ejecutable. Una sonda no nula comprueba también permisos de su propietario. Dependencia indisponible: 503 genérico. |
| GET /transfers?limit=50&offset=0 | Página privada: items, limit, offset y has_more. Limit 1..200; offset 0..10000. Orden created_at e ID descendentes, con una fila extra para determinar has_more. |
| POST /transfers | Crea un evento propio; 200. Cada POST es una operación nueva, sin deduplicación por nombre ni reintento automático tras perder una respuesta. |
| PATCH /transfers/{transfer_id} | Cambia solo campos enviados de un evento propio; 200. Evento ajeno o inexistente: 404 Transfer not found. Conflicto de estado/progreso: 409. |
| DELETE /transfers/history | Borra hasta 1000 terminales propios por petición, empezando por los más antiguos; devuelve count efectivo. Repetir hasta count=0 retira los terminales disponibles. |

Cada evento responde transfer_id, owner_user_id, document_id, filename, direction, status, progress, size_bytes, metadata, created_at y updated_at. Nunca incluye rutas de almacenamiento ni contenido documental. La forma paginada exige desplegar backend y frontend juntos.

## Entradas y errores

| Campo | Regla |
| --- | --- |
| filename | 1..512 caracteres Unicode válidos; conserva espacios de extremos y rechaza nombres blancos y controles C0/DEL. Es una etiqueta, nunca una ruta para abrir archivos. |
| document_id / transfer_id de PATCH | Texto de 1..128 caracteres, no blanco, sin controles o Unicode inválido. No exige UUID para conservar IDs históricos válidos. |
| direction / status | UPLOAD o DOWNLOAD; estados PENDING, RUNNING, COMPLETED, FAILED, CANCELLED. |
| progress | Entero estricto 0..100, sin conversión de cadenas, booleanos o floats. Representa etapas informadas por el cliente, no bytes medidos. |
| size_bytes | Entero estricto 0..9223372036854775807, compatible con BIGINT. Cero es conocido; null es desconocido. |
| metadata | Objeto JSON de hasta 16384 bytes UTF-8 compactos, sin escapes ASCII; hasta 16 niveles desde la raíz en 0. Claves, valores y elementos incrementan nivel. Sin NUL, NaN/Infinity o Unicode inválido. |
| Cuerpo HTTP | Hasta 65536 bytes reales, contados por fragmentos con o sin Content-Length fiable; exceso: 413 antes del parseo/ruta. No es un timeout de lectura ni control de tasa. |
| Campos extra | 422; incluye owner_user_id, metadata_ y campos inmutables enviados en PATCH. |

En PATCH, ausente conserva; document_id/size_bytes null retiran; metadata reemplaza el objeto entero y {} lo vacía. Otros nulos y PATCH vacío se rechazan. Crear admite document_id/size_bytes nulos, pero metadata requiere objeto. metadata HTTP se mapea a metadata_ ORM y persiste en la columna JSONB; no se inventan datos históricos que antes no llegaron a guardarse.

Los 422 normalizan ubicaciones y omiten valores, contexto y claves arbitrarias. JSON malformado o excesivamente profundo se rechaza con 400/422 privado según la fase de validación. SQLAlchemy y errores internos devuelven 500 genérico; las escrituras revierten la sesión. Las validaciones de dominio mantienen 400 y las referencias/eventos ajenos o inexistentes mantienen 404. No se reflejan credenciales ni detalles SQL.

## Identidad y referencias documentales

Listar, modificar y limpiar siempre filtran por dueño del evento; ser administrador no abre el historial de otra persona. Revocar lectura documental no elimina nombres/metadatos del diario personal ni permite descargar el documento a través de ese diario.

Crear con document_id o enviarlo no nulo en PATCH exige lectura vigente según la política de Library/Access:

- Dueño: columna owner_user_id; fallback metadata.owner_user_id solo si es SQL NULL. Una columna vacía o distinta tiene precedencia.
- Asignación como destinatario/remitente, con estado distinto de CANCELLED/EXPIRED.
- Administración del tenant resuelto, con columna tenant_id y fallback JSON solo si es NULL.
- Grupo presente en el JWT, limitado a los tenants de membresía o a un documento sin tenant.
- Superadmin puede referenciar documentos globalmente, conservando su historial privado.

No exige PROCESSED, embeddings ni allow_download para registrar: Transfer no ejecuta ni autoriza la descarga. Documento ajeno o inexistente: el mismo 404 Document not found. PATCH comprueba primero la propiedad del evento. Cada referencia enviada se revalida, aunque sea la anterior; omitirla permite corregir el diario tras revocación y null la retira.

La FK SQL de transfer_events.document_id existe y usa ON DELETE SET NULL, aunque el ORM sea una proyección sin ForeignKey. Borrar un documento conserva evento y nombre; limpiar historial conserva documentos y archivos. No hay caducidad automática. No se usa create_all como migración.

## Estados y concurrencia

| Estado actual | Siguientes admitidos |
| --- | --- |
| PENDING | PENDING, RUNNING o cualquier terminal. |
| RUNNING | RUNNING, COMPLETED, FAILED o CANCELLED. |
| Terminal | Solo el mismo estado. Una nueva operación crea otro evento. |

El progreso nunca disminuye y queda congelado al terminar. PENDING/RUNNING admiten 0..100; llegar a 100 por sí solo no termina la operación. FAILED/CANCELLED conservan la última etapa si se omite progress. COMPLETED exige 100: crear otra combinación devuelve 400; un PATCH incompatible devuelve 409 sin cambios parciales. El servidor no infiere resultados ni completa porcentajes omitidos.

Un PATCH idéntico no emite otro UPDATE ni altera fechas; una referencia enviada sigue revalidándose. Un terminal admite correcciones de metadatos, tamaño o referencia sin reabrirse. Datos históricos incoherentes se conservan o limpian; reparar estado/progreso requiere una decisión explícita.

Todas las escrituras toman un advisory lock transaccional por propietario. PATCH vuelve a leer con FOR UPDATE/populate_existing. Al adjuntar un documento el orden es dueño → documento (KEY SHARE mediante función acotada) → evento, compatible con DELETE documental/SET NULL. Si borra primero, la referencia responde 404; si vincula primero, el borrado espera. No se bloquea el documento al corregir solo el diario o retirar el vínculo.

Alta/PATCH cargan y separan la respuesta del ORM antes de commit, manteniendo bloqueos. Una limpieza inmediata no convierte un éxito en fallo por refresh de una fila retirada. Si commit falla, se revierte y no se devuelve éxito. DELETE usa un único SQL con subconsulta limitada a 1000, ordenada por created_at e ID; no materializa eventos en Python ni cuenta dos veces una limpieza concurrente.

El protocolo coordina escritores de Transfer; no impone reglas a SQL externo ni serializa todos los cambios simultáneos de permisos. La autorización consulta el estado visible en la comprobación y mantiene los claims del JWT hasta renovación/expiración, como los demás servicios.

## Consumidores y límites del diario

La web carga páginas de 50, muestra todos los registros cargados por scroll y ofrece Actualizar/Cargar más. El contador es de filas cargadas, no total global. Deduplicar no cambia el avance por tamaño bruto de página. Offset no es una instantánea: altas/limpiezas externas pueden mover posiciones; refresca ante cambios y al alcanzar la cota de offset. Las escrituras propias reinician la ventana en primera página.

El controlador por cliente/generación descarta respuestas y avisos antiguos tras refresh, desmontaje o reinicio de efectos de React. Clics repetidos de paginación/limpieza no duplican peticiones. Cargar más conserva filas ante fallos; limpiar conserva activos en caché incluso si falla la recarga. El adaptador rechaza contratos antiguos o incompletos, no los disfraza de lista vacía.

Search, carga desde Chat y descarga comparten flujos que ejecutan el archivo una vez sin esperar al diario. La cola independiente ordena alta → etapa 65, si corresponde → terminal. Fallos o peticiones pendientes de alta/PATCH no bloquean el resultado documental. Su error original se propaga intacto aunque también falle guardar FAILED. Los fallos omiten progreso obsoleto y una referencia repetida que podría haberse revocado.

Las advertencias se muestran fuera del modal, sobreviven al refresh y pueden cerrarse. Un cliente retirado no inicia pasos pendientes del diario ni publica avisos en el siguiente. Descartar una respuesta no revierte una petición ya confirmada; cerrar la pestaña no garantiza terminar la cola. Este historial no es entrega duradera ni auditoría autoritativa.

## Operación

Prepara .env según el [README raíz](../../README.md). Para Transfer solo se necesitan PostgreSQL y Auth; no IA, embeddings, OAuth, documentos montados ni claves privadas. El servicio no carga .env automáticamente: Compose interpola once variables explícitas, con CORS local para localhost:3000/127.0.0.1:3000 y sin credenciales de navegador.

| Ajuste Compose | Predeterminado / semántica |
| --- | --- |
| TRANSFER_DB_PASSWORD | blandskron-local-transfer, solo desarrollo local; PGPASSWORD del rol document_transfer_runtime. La contraseña no va en DATABASE_URL. |
| TRANSFER_CORS_ORIGINS | Arreglo JSON con http://localhost:3000 y http://127.0.0.1:3000. |
| TRANSFER_DB_POOL_MIN_SIZE | 1; tamaño retenido 1..100, conexiones creadas bajo demanda, sin precalentamiento. |
| TRANSFER_DB_POOL_MAX_SIZE | 10; capacidad total 1..100 y al menos el tamaño retenido. |
| TRANSFER_DB_TIMEOUT_SECONDS | 30; 1..300 segundos para espera del pool y connect_timeout, no para duración de consultas. |

Las demás variables son APP_ENV, APP_NAME, LOG_LEVEL, DATABASE_URL, AUTH_JWT_PUBLIC_KEY_PATH y AUTH_JWT_ALGORITHM=RS256. La configuración inválida detiene el arranque. El pool usa pre_ping; la sesión cierra/revierte trabajo no confirmado y el lifespan libera conexiones con finally, incluso tras fallos.

Para actualizar una instalación, respalda la base y detén Transfer antiguo antes de levantar la nueva versión; evita escritores antiguos/nuevos en paralelo. Desde la raíz:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml stop document-transfer-service
docker compose -f docker/docker-compose.yml up -d --build --wait document-transfer-service
curl http://localhost:8007/api/v1/health
curl http://localhost:8007/api/v1/health/db
# Reaplicación intencional: mantiene y verifica el alcance del rol.
docker compose -f docker/docker-compose.yml run --rm --no-deps transfer-db-role
```

Compose espera al esquema y a los roles antes de arrancar Transfer. Ejecuta UID/GID 10007 con capacidades retiradas y no-new-privileges; solo monta la clave pública de Auth en lectura. Reinicia Transfer al rotar claves: autenticación mantiene caché por ruta, mientras readiness relee el archivo. Liveness no depende de la base; readiness comprueba sus dependencias, no todos los índices/restricciones.

## Permisos de PostgreSQL

| Rol / objeto | Alcance |
| --- | --- |
| document_transfer_runtime | SELECT del historial; INSERT en dueño/referencia/nombre/dirección/estado/progreso/tamaño/JSON; UPDATE solo referencia/estado/progreso/tamaño/JSON/updated_at; DELETE del historial. Sin modificar dueño, nombre, dirección, ID o created_at. |
| Lectura de referencias | documents: document_id, tenant_id, owner_user_id, metadata. document_assignments: assignment_id, document_id, assigned_to_user_id, assigned_by_user_id, status. Sin acceso a otras columnas documentales ni a embeddings, Auth o tablas de empresas. |
| document_transfer_reference_owner | Sin login; SELECT/UPDATE solo de documents.document_id para tomar KEY SHARE mediante public.transfer_lock_document_reference(text). Runtime no recibe UPDATE documental. |
| Función de referencia | SECURITY DEFINER, STRICT, search_path pg_catalog/pg_temp, tabla public.documents cualificada, sin SQL dinámico. Solo propietario/runtime pueden ejecutar; sin PUBLIC, otros ejecutores o delegación por runtime. |

Ambos roles carecen de superusuario, creación de bases/roles, herencia, replicación, bypass RLS y membresías; no pueden crear en public. El verificador compara columnas/operaciones efectivas, secuencias, atributos y ACL. Permisos excesivos o delegables bloquean la comprobación y requieren revisión explícita. El aprovisionamiento es transaccional/repetible y usa el bloqueo global de roles. El rol es compartido por el servicio; la privacidad por usuario se aplica mediante JWT/filtros, sin RLS personal.

Antes de reparar propietarios históricos, ejecuta la auditoría de solo lectura desde PowerShell:

```powershell
Get-Content scripts/database/transfer/audit_owners.sql | docker compose -f docker/docker-compose.yml exec -T postgres psql -U postgres -d documents_db -v ON_ERROR_STOP=1
```

En bash, usa la misma llamada psql con redirección `< scripts/database/transfer/audit_owners.sql`. Devuelve categorías/conteos sin imprimir IDs, reasignar o borrar. Incluso un owner numérico canónico podría provenir de un antiguo sub/username: no prueba autoría. Preserva registros ambiguos y exige respaldo/evidencia/decisión antes de repararlos. Los owners no canónicos no son alcanzables por la nueva identidad canónica.

## Validación y límites de la evidencia

Desde la raíz, con el servicio saludable:

```sh
docker compose -f docker/docker-compose.yml run --build --rm --no-deps transfer-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps transfer-tests ruff check --no-cache app tests
docker compose -f docker/docker-compose.yml exec -T document-transfer-service python -m pip --no-cache-dir check
docker compose -f docker/docker-compose.yml run --build --rm --no-deps transfer-audit
```

Desde frontend: npm ci, npm test y npm run build. La suite backend tiene 317 casos PostgreSQL/HTTP; frontend tiene 60 pruebas de contratos, controlador, flujos y render SSR. Cubren identidad, permisos, referencias/revocación, metadatos y nulos, límites/errores privados, estados, lotes, 207 eventos empatados y páginas 100/100/7, recuperación y carreras con esperas Lock observadas. Los escritores concurrentes usan login real document_transfer_runtime; preparar datos o simular borrado documental corresponde a conexiones administrativas distintas.

Las pruebas usan claves/datos sintéticos, rollback o limpieza por IDs/propietarios sintéticos. Drift y readiness se prueban en bases aisladas que se retiran por nombre comprobado. Requieren TRANSFER_TEST_DATABASE_URL administrativa explícita y DATABASE_URL/PGPASSWORD runtime; Compose configura ambas. No usan create_all ni migran tablas compartidas; no ejecutar en producción. La suite conserva una deprecación del adaptador de pruebas httpx de Starlette, fuera de runtime.

CI valida Compose/UID/herramientas, arranque limpio, roles repetidos, auditoría, pruebas y reinicio sobre el volumen existente. La revisión de cierre comprobó un recorrido HTTP real con access/renovación de Auth, rol mínimo y dos usuarios: privacidad incluso frente a administrador, JSON, preservación documental al limpiar, SET NULL al borrar documentos, activos conservados y contadores. Se verificaron limpieza de eventos/documentos sintéticos y rollback de ambos usuarios; los consumidores aprobaron sus 60 pruebas y build. También se importaron los 30 módulos vigentes tras retirar cinco archivos y cuatro símbolos sin consumidores. Es validación funcional del servicio, no auditoría exhaustiva de seguridad, accesibilidad o recorrido visual completo de navegador. El cierre transversal del sistema está integrado; la evidencia está en docs/release/.

## Verificación de dependencias e imagen

El runtime usa FastAPI 0.162.0, Starlette 1.10.0, PyJWT 2.15.1, cryptography 50.0.2, python-dotenv 1.2.4 y pip 26.3. pytest 9.0.3 queda solo en test. pip-audit 2.10.1 auditó el inventario congelado **antes** de instalar sus propias dependencias: no reportó avisos en las 30 distribuciones del runtime. Esto no equivale a ausencia general de vulnerabilidades.

El 6 de noviembre de 2026 se reconstruyó con --pull y se escaneó el artefacto exportado mediante Trivy 0.74.0, solo vulnerabilidades HIGH/CRITICAL. Base python:3.12-slim: `sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54`. Manifiesto del runtime auditado: `sha256:28cdb65f8ccf693688c660abea53e980612c20f6a27d9d671f9a6a3d15a012e4`; ImageID del informe: `sha256:b7fb3fb73d59191cdaf82a1cdbf6910182ddc6c1a5ca3480966a7e32befd4b7f`. SHA-256 del informe JSON: `070a1493d2192e8eaa7e5f4a128707c038270d58f4e25bbadfdeca381321b23f`.

| Alcance | Resultado observado | Seguimiento |
| --- | --- | --- |
| Debian 13.7, 87 paquetes detectados | 49 coincidencias altas por paquete; 13 CVE distintos; cero críticos y ninguna versión corregida indicada por Trivy. | TRANSFER-F01: reconstruir/repetir escaneo y resolver o registrar disposición antes de despliegue público. |
| Python instalado | pip-audit sin avisos; setuptools no figura como distribución instalada. | Mantener auditoría del inventario realmente construido. |
| Metadatos vendorizados | Trivy reporta CVE-2025-47273 en setuptools 70.3.0 e indica 78.1.1. pip 26.3 conserva esa declaración en _vendor/vendor.txt. | TRANSFER-F02: revisar actualización upstream y repetir escaneo. Instalar otro setuptools no sustituye esa copia ni demuestra corrección. |

Los CVE distintos de Debian son CVE-2025-69720, CVE-2026-119373, CVE-2026-119374, CVE-2026-119379, CVE-2026-16742, CVE-2026-54369, CVE-2026-76642, CVE-2026-76844, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410, CVE-2026-85091 y CVE-2026-9538. La suma es 50 coincidencias altas de Trivy contando el aviso vendorizado, no 50 vulnerabilidades únicas instaladas. No se validó explotación de cada aviso ni se trasladan estos conteos a otras imágenes; la evidencia de la reconstrucción transversal está en docs/release/.

Para reproducir el escaneo sin montar el socket Docker, construye el runtime con --pull, expórtalo mediante docker save y ejecuta Trivy sobre ese archivo; por ejemplo desde la raíz en bash:

```sh
docker build --pull -t blandskron-transfer-audit backend/DocumentTransferServices
audit_dir="$(mktemp -d)"
docker save -o "$audit_dir/runtime.tar" blandskron-transfer-audit
docker run --rm -v "$audit_dir:/audit" -v blandskron-trivy-cache:/root/.cache/trivy aquasec/trivy:0.74.0 image --scanners vuln --severity HIGH,CRITICAL --format json --output /audit/trivy.json --input /audit/runtime.tar
```

Usa un directorio temporal para estos artefactos y no los agregues a Git. El resultado depende de la imagen y de la base de avisos del momento. Los seguimientos son visibles; no se ocultan CVE, no se declara libre de riesgos la imagen y no se presenta esta comprobación como escaneo de secretos o auditoría exhaustiva del código.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE).
