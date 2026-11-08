# DocumentExportServices

Exporta a PDF una instantánea de pregunta, respuesta y fuentes aportada por el cliente. La identidad y las referencias se validan; el contenido no se certifica ni se recupera desde documentos, historial o LLM. No hay descargas remotas desde el renderer.

**Estado:** EXPORT-004/005 integrados; EXPORT-006/007 se entregan juntos: historial/coordinación web y operación con rol mínimo/imagen auditada. Resta EXPORT-008 para el cierre integral. [Tablero](../../ROADMAP.md#documentexportservices).

## Contrato actual

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness público |
| GET | `/api/v1/health/db` | Readiness de clave y columnas/esquema DB; 503 saneado |
| POST | `/api/v1/exports/chat-message/pdf` | PDF y metadatos en una transacción; 200 con DTO |
| GET | `/api/v1/exports` | Página propia: limit 1..50 (20 por defecto), before y source_type opcionales |
| GET | `/api/v1/exports/{export_id}` | Metadatos propios o 404 |
| GET | `/api/v1/exports/{export_id}/status` | COMPLETED, MIGRATION_REQUIRED o EXPIRED |
| GET | `/api/v1/exports/{export_id}/download` | Bytes PDF verificados; 409 si requiere migración, 410 expirado |
| DELETE | `/api/v1/exports/{export_id}` | Elimina fila/PDF binario propio; nunca archivos heredados |

El DTO conserva los campos anteriores y añade sha256/expires_at. No devuelve dueño, ruta, bytes, claims ni huella de contraseña. Nombre ASCII saneado coherente entre DTO y Content-Disposition; MIME application/pdf, Cache-Control private/no-store y nosniff. El checksum también se usa en ETag privado. IDs de export y source_type están acotados; las rutas ajenas devuelven 404 incluso para administradores.

Todas las rutas funcionales exigen RS256, user_id entero positivo canónico, exp/iat coherentes, jti acotado, token_type=access y hash_password de Auth. No hay fallback a username/sub/unknown. La cuenta debe existir, estar activa y conservar su huella; errores SQL de identidad devuelven 503, tokens rechazados 401. FOR SHARE conserva la vigencia durante la transacción. Logout de refresh no equivale a revocación individual de todos los access tokens. La vigencia se comprueba mediante export_identity_is_current; el runtime no lee contraseñas ni tablas de identidad directamente.

Conversación y mensaje son opcionales. Si llegan, se validan ambos dueños y coherencia antes de generar; referencias inválidas/ajenas reciben el mismo 404. Campos vacíos/desconocidos reciben 422. Las referencias se bloquean hasta terminar la transacción. La web omite IDs locales local-* / blandskron-* aún no sincronizados: conserva la conversación remota si solo falta el mensaje. No reintenta referencias rechazadas quitándolas ni convierte la instantánea en historial certificado.

## Límites y PDF

| Recurso | Límite |
| --- | --- |
| Cuerpo HTTP real, incluido chunked | 256 KiB; 15 segundos de recepción |
| POST simultáneos | 2 por proceso; exceso 503 con Retry-After |
| Título / pregunta / respuesta | 160 / 8.000 / 50.000 caracteres |
| Referencias / IDs de fuente / filename | 128 / 128 / 256 caracteres |
| Fuentes | 40, tipadas; content/snippet/chunk hasta 2.000 cada uno |
| Página y score | Entero positivo; score finito |
| Metadata | 8 KiB JSON, profundidad 4, 256 nodos, claves 64, strings 2.048; números finitos y enteros de 64 bits |
| PDF | 20 páginas y 1 MiB |
| Render aislado | 15 segundos de pared; en Linux 256 MiB de memoria virtual y 15 segundos CPU |
| Cuota por dueño | 100 exportaciones o 50 MiB de tamaños registrados, lo que se alcance primero |
| Capacidad global de PDF binario | 500 MiB lógicos; metadata/índices/TOAST/WAL/copias requieren capacidad adicional |
| Retención de PDFs binarios | 30 días; expirados no se descargan y siguen consumiendo cuota hasta borrado/purga explícitos |

Los límites están en [export_limits.py](app/config/export_limits.py). Se limitan los bytes recibidos aunque Content-Length mienta o no exista. Un proceso hijo por render recibe solo datos y entorno mínimo, sin credenciales de DB/IA. El padre mata y recoge al hijo al vencer el plazo. El cuerpo excesivo o un PDF fuera de límites devuelve 413; validaciones 422 sin reflejar entradas. Pool y sentencias SQL mantienen sus propios timeouts; no se promete un único plazo de pared para toda la petición/DB/red. Varias réplicas multiplican el límite local de POST; las cuotas SQL se coordinan entre procesos.

Texto plano UTF-8 normalizado NFC. Markdown y HTML se imprimen literalmente; no se interpretan imágenes, enlaces o recursos activos. En snippets de la tabla se compacta espacio en blanco para mantener filas legibles. Paragraph hace wrapping, las filas permanecen completas y los encabezados se repiten por página. Noto Sans Regular/Bold se embebe con su [licencia SIL OFL 1.1 y hashes](app/infrastructure/pdf/fonts/README.md). Se admiten los glifos comunes a ambas fuentes, incluidos latín, griego y cirílico; caracteres no cubiertos (p. ej. CJK/emoji), controles y formato bidi se rechazan antes de renderizar, sin cuadros de sustitución silenciosos.

## Historial y coordinación web

GET /exports cambia de array a `{items, next_cursor}`; actualizar la web y los consumidores junto al backend. El cursor opaco acota fecha/ID y está asociado a dueño/filtro, con validación estricta; no es una credencial. SQL conserva el filtro owner en todas las páginas. Orden DESC created_at/export_id, índice por dueño/fecha/ID y consulta limit+1; un registro nuevo aparece al actualizar y borrar el registro del cursor no rompe el siguiente tramo. Cursor de otra cuenta/filtro o malformado: 400; límites inválidos: 422. No se divulga un total ni se cargan bytes PDF en el listado. Metadatos y errores llevan private/no-store y Vary Authorization.

En el chat, **Mis PDFs** abre un diálogo con foco contenido, Escape/cierre y devolución de foco al botón. Muestra estados, descarga, borrado, actualizar y cargar más. El contador refleja registros cargados. Los PDFs expirados o por migrar no ofrecen descarga. El historial es por usuario, no una partición documental por tenant; un cambio de cuenta/tenant reinicia la vista y cancela operaciones pendientes.

Cliente de sesión estable durante refresh, renovando solo credenciales. Antes/después de cada petición verifica sesión/cuenta/tenant; el controlador añade generación, AbortController y versión para ignorar respuestas tardías, incluso si el transporte no respeta abort. Cambiar conversación o desmontar descarta la operación anterior. Doble envío se bloquea síncronamente; cancelar no promete deshacer un commit ya confirmado, por eso el reintento conserva Idempotency-Key. Conflictos/expiración/exceso de tamaño permanecen visibles y accionables.

La descarga valida MIME, firma y máximo de 1 MiB antes de crear un object URL. Se comprueba vigencia de la operación antes de tocar DOM; enlace y URL se liberan con finally incluso si append/click/remove falla. Nombres seguros provienen del DTO coherente con Content-Disposition. Cuenta/tenant cambiado no puede publicar errores, refrescar credenciales ni descargar un resultado anterior. El cliente de sesión compartido conserva los contratos existentes de Profile.

## Persistencia, recuperación e idempotencia

[bytea de PostgreSQL](https://www.postgresql.org/docs/16/datatype-binary.html) permite confirmar bytes y fila juntos. No se crean PDFs/temporales en el filesystem del servicio. Fallar o matar el renderer no deja recursos persistentes; fallar DB revierte la transacción. La descarga obtiene metadatos y bytes en una consulta con FOR SHARE, impidiendo que borrado/purga intercalen una fila perdida. Se comprueba tamaño/firma PDF y SHA-256 antes de devolver datos. La DB impone además correspondencia tamaño/checksum y máximo de 1 MiB. Los listados difieren la carga de bytes.

La cuota se serializa por dueño y la capacidad global se comprueba bajo advisory lock antes de insertar. No se descartan silenciosamente archivos ni exportaciones al alcanzar cuota: 409. Con fuentes pequeñas las muestras midieron 30.771–34.236 bytes y 1–4 páginas; [evidencia sintética](docs/PDF_QA.json). Los límites lógicos no equivalen a espacio físico reservado: monitorizar pg_total_relation_size, WAL, backups y crecimiento antes de despliegue público.

POST admite `Idempotency-Key` UUID opcional. Mismo dueño, clave y request normalizado devuelven la misma exportación sin renderizar de nuevo, también después de reinicio o pérdida de respuesta. Misma clave con contenido distinto o registro expirado devuelve 409. El índice único evita duplicados entre procesos. Una clave identifica una operación, no message_id: se permite exportar nuevas instantáneas del mismo mensaje. Tras DELETE/purga la clave deja de reservarse. La web conserva la clave durante reintentos ambiguos; si la creación ya devolvió un ID y falla la descarga, reintenta ese PDF sin crear otro. Al completar o cambiar la instantánea se inicia una operación nueva.

La retención es explícita: no hay cron oculto ni borrado automático de fuentes. DELETE libera la fila propia; el mantenimiento usa [purge_expired.py](../../scripts/export/purge_expired.py), dry-run por defecto y `--apply` para borrar únicamente PDFs binarios expirados. Cuenta eliminada/inactiva no autoriza sus filas conservadas; revisión administrativa/retención no reasigna dueño.

## Rol mínimo y artefacto

[provision_role.sql](../../scripts/database/export/provision_role.sql) se ejecuta como administrador después de esquema y Auth, antes de arrancar Export; transacción y advisory lock comunes a provisión. Admite EXPORT_DB_PASSWORD (default público de desarrollo en .env.example; usar credencial distinta en despliegue). Role export_runtime LOGIN sin membresías/superusuario/CREATE/RLS bypass: SELECT de columnas públicas y bytes de document_exports, INSERT explícito y DELETE; no UPDATE, rutas heredadas, error_message, Auth, contenido documental o conversaciones. El aislamiento por dueño se aplica en las consultas del servicio; el rol no es RLS por usuario final.

Tres helpers booleanos SECURITY DEFINER con owner export_helper_owner NOLOGIN y search_path fijo pg_catalog/pg_temp: export_identity_is_current, export_references_are_owned y export_lock_owned. Acceso mínimo de ese owner a columnas de identidad/referencias e IDs para FOR SHARE; no devuelve contraseñas ni contenido. EXECUTE revocado a PUBLIC y concedido solo al runtime. [verify_role.sql](../../scripts/database/export/verify_role.sql) inspecciona atributos, cada columna/operación, delegación, secuencias, funciones privilegiadas, owner/ACL/search_path/strictness. Un privilegio inesperado detiene la provisión para reparación explícita, sin integración parcial. Las pruebas incluyen login real y SQLSTATE 42501 para accesos prohibidos; no confunden SET ROLE desde superusuario con un login restringido.

[IMAGE_AUDIT.json](docs/IMAGE_AUDIT.json) registra la imagen local exacta, archivo SHA-256, config, base, inventario de 32 distribuciones, paquetes SO e inputs normalizados. Trivy 0.76.2, 8 de noviembre de 2026: **47 coincidencias HIGH en 11 CVE Debian, cero críticos y sin versión corregida indicada**. EXPORT-F01/PLAT-002 exige reconstruir/reevaluar antes de despliegue público; no equivale a explotación validada ni se suprimen avisos. Tras quitar pip, el escáner dejó de informar la declaración setuptools vendorizada; el runtime no conserva instalador ni esa copia. pip-audit del inventario funcional sin avisos. Las cuatro alertas npm permanecen en WEB-001.

[audit_image.py](../../scripts/export/audit_image.py) exporta/hashea el artefacto y escanea ese archivo con scanner fijado por digest; conserva todas las coincidencias y detiene avisos críticos o casos sin disposición. No monta docker.sock en el scanner ni lee configuración/DB/documentos. La atribución de findings se limita a lo que indica el escáner; no es una prueba de explotabilidad. CI repite sobre su propia imagen y publica los JSON como artefacto export-image-audit; su digest puede diferir del build local. No presentar el conteo local como escaneo de otra imagen.

## Actualizar una instalación existente

1. Respaldar DB y archivos existentes. Detener Export durante la actualización para impedir nuevas escrituras del código anterior. No borrar ni mover `documents/exports`.
2. Con PostgreSQL/Auth existentes, ejecutar el orquestador `database-schema` (run_all.sql incluye [pdf_storage.sql](../../scripts/database/export/pdf_storage.sql)). La migración es aditiva y repetible; tipos parciales incompatibles detienen la transacción para reparación explícita. No rellena PDFs ni altera dueños. Las instalaciones nuevas siguen el arranque normal del README raíz.
3. Ejecutar [audit_owners.sql](../../scripts/database/export/audit_owners.sql) con acceso administrativo: solo conteos. Filas username/unknown o sin cuenta actual requieren revisión; no inferir propiedad por nombre de archivo.
4. Aprovisionar export-db-role (ver rol mínimo) y reconstruir Export y web juntos. El runtime ya no monta exports ni comprueba escritura en ese directorio. Las filas antiguas aparecen como MIGRATION_REQUIRED y no se descargan desde rutas persistidas, aunque apunten a un archivo existente.
5. Inventariar/migrar lotes revisados con el procedimiento siguiente. No quitar los originales después: su conservación y eventual eliminación requieren una política/aprobación propia.

Desde la raíz, con servicios de DB ya disponibles:

```powershell
docker compose -f docker/docker-compose.yml stop document-export-service
docker compose -f docker/docker-compose.yml run --rm --no-deps database-schema
docker compose -f docker/docker-compose.yml up -d --build --wait document-export-service
```

### Migración revisada de PDFs heredados

[migrate_legacy.py](../../scripts/export/migrate_legacy.py) requiere `EXPORT_MIGRATION_DATABASE_URL` y credencial de proceso separada. Se ejecuta en el target export-tests, que incluye pypdf, con el directorio legado montado **solo lectura** y un directorio privado de revisión. Debe usar POSIX con O_NOFOLLOW/dir_fd (Linux); no hay fallback inseguro en Windows. Las rutas de DB deben corresponder exactamente al directorio montado indicado en `--base` (por ejemplo /app/exports en instalaciones anteriores). No reescribir rutas masivamente para hacerlas coincidir: revisar el inventario de esa instalación.

Ejemplo de comandos dentro del entorno de mantenimiento, con DB/volúmenes explícitos y fuera de tráfico de actualización:

```text
python /export-checks/migrate_legacy.py --base /app/exports --manifest /review/batch.json --limit 100
python /export-checks/migrate_legacy.py --base /app/exports --manifest /review/batch.json --apply
python /export-checks/purge_expired.py
python /export-checks/purge_expired.py --apply
```

El primer comando crea un manifest nuevo (0600; no sobreescribe) con IDs/dueño/checksum/tamaño/estado, sin rutas ni contenido documental; protegerlo como inventario privado. Revisar y conservar solo entradas ready aprobadas antes de `--apply`. Se rechazan dueño no resuelto, archivos cambiantes/ausentes, enlaces en archivo o ancestros, FIFO/dispositivos, tamaño excesivo/discrepante, PDF inválido/cifrado, formularios, acciones o anotaciones. El runtime no abre ninguno de esos recursos. La lectura por descriptores confina al basename dentro de la base sin seguir enlaces; no modifica el archivo original.

Apply bloquea filas/capacidad, verifica de nuevo el checksum y el inventario aprobado y confirma el lote en una transacción. Cualquier discrepancia revierte todo el lote. Repetir un lote ya copiado con los mismos hashes es no-op verificable. No es una reparación de propiedad ni un sanitizador universal de PDFs: las entradas review_required se conservan para decisión explícita. Inventario y copia no se ejecutaron contra datos personales durante este incremento.

## Ejecución actual

`uvicorn app.main:create_app --factory --port 8016`, sin dotenv ni conexiones/archivos al importar. Son obligatorios DATABASE_URL (postgresql+psycopg) y AUTH_JWT_PUBLIC_KEY_PATH absoluto. PGPASSWORD separa la contraseña de la URL. EXPORT_STORAGE_BASE_PATH se acepta opcionalmente por compatibilidad y se ignora en runtime; el migrador exige --base explícito.

CORS_ORIGINS es JSON de orígenes explícitos (local por defecto; [] deshabilita acceso cruzado). RS256 fijo. Pool mínimo/máximo 1/10, máximo total 100 y timeout 30 segundos (1..300) para conexión/pool/sentencias. Compose usa EXPORT_CORS_ORIGINS y EXPORT_DB_*; no inyecta env_file global. Readiness comprueba clave pública RSA y columnas DB nuevas, sin filesystem de documentos. El runtime usa export_runtime, UID/GID 10009, filesystem de solo lectura, cap_drop ALL, no-new-privileges, 768 MiB/2 CPU/96 procesos y /tmp tmpfs noexec de 16 MiB. No incluye pip ni herramientas test/audit. La base Python está fijada por digest y aplica actualizaciones Debian durante el build; la auditoría vincula imagen/archivo/config/input hashes.

## Verificación

Desde la raíz, sobre esquema/DB sintéticos:

```powershell
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml run --build --rm --no-deps export-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps export-tests ruff check --no-cache app tests /export-checks
docker compose -f docker/docker-compose.yml run --build --rm --no-deps export-audit
python scripts/export/audit_image.py --image <runtime-image> --out <directorio-nuevo-de-auditoria>
```

El target audit verifica un inventario de las dependencias del runtime sin incluir pip; las herramientas se instalan después de congelarlo. El build valida pip check antes de retirar el instalador y verify_runtime_dependencies.py verifica el grafo capturado después, incluidos extras uvicorn/psycopg, sin instalar herramientas en runtime.

Fuera de Compose, entorno aislado con requirements.txt + requirements-test.txt: `python -m pytest -q -p no:cacheprovider -m "not postgres" tests`. PostgreSQL requiere EXPORT_TEST_DATABASE_URL explícita y base sintética; no se omite si falta. CI ejecuta también login/refresh reales de Auth para tres roles, PDFs propios, privacidad, revocación y limpieza. La suite incorpora cuotas, repetición/reinicio de operación, migración/checksum/cambios de archivo, POSIX, retención, constraints y concurrencia.

[scripts/export/render_samples.py](../../scripts/export/render_samples.py) genera tres fixtures sintéticos; renderizar cada página con Poppler y revisar extracción/texto/glifos y layout. La revisión local final cubrió las seis páginas con fuentes embebidas, entidades literales resueltas y tablas legibles; [PDF_QA.json](docs/PDF_QA.json) registra tamaños/hashes. PDFs/PNG temporales no se añaden al repo. Docker local disponible en EXPORT-006/007: 202 pruebas PostgreSQL/Linux, aprovisionamiento repetido, login real del rol, JWT reales para tres roles y reinicio aprobados, sin montar documentos personales. Frontend: npm ci/test/build; las cuatro alertas altas npm siguen en WEB-001. Dos deprecaciones de dependencias (TestClient/httpx y ReportLab/ast.NameConstant) permanecen en seguimiento.

## Evidencia de EXPORT-001

El [BASELINE.json](docs/BASELINE.json) conserva el análisis histórico sobre 454fdcedd30f671cdf5dddfdf66be53a2c46f780: 33 módulos, sondas con repositorio sustituido sin PostgreSQL/Auth/lifespan, CORS abierto, JWT incompletos, ausencia de límites, archivos huérfanos/estados obsoletos y problemas de glifos/tablas. Encontró 46 avisos Python Windows en cinco paquetes; no fue escaneo de imagen ni explotación validada. EXPORT-002 sustituyó configuración/dependencias y aprobó 57 pruebas; EXPORT-003 aprobó 138 más recorrido Auth real (PR #69). Es evidencia anterior, no comportamiento esperado actual.

## Decisiones y mejoras por incrementos

- EXPORT-004/005: este paquete conjunto, límites/PDF y persistencia binaria con migración conservadora.
- EXPORT-006/007: paquete actual; 202 pruebas PostgreSQL, 98 Node, seis Chromium, build, Ruff, Compose y auditorías ejecutados localmente; consultar checks del PR para CI.
- EXPORT-008: instalación/actualización y cierre de extremo a extremo; después DRIVE-001. Solo se cierran tarjetas con evidencia cumplida, no por agruparlas.

## Licencia

[LICENSE raíz](../../LICENSE) para el proyecto; [SIL OFL](app/infrastructure/pdf/fonts/LICENSE.txt) para Noto Sans sin modificar. Se añaden fuentes redistribuibles y fixtures de código, no documentos personales ni PDFs generados.
