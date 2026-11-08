# DocumentExportServices

Convierte una instantánea de una respuesta de chat en PDF y conserva metadatos y archivo para su descarga por dueño. No consulta el LLM ni recupera documentos o mensajes: pregunta, respuesta y fuentes llegan desde el cliente.

**Estado:** EXPORT-002 incorpora factory, configuración explícita, readiness y suite mantenida. El servicio sigue en modernización. El diagnóstico histórico EXPORT-001 corresponde a `454fdcedd30f671cdf5dddfdf66be53a2c46f780`; su inventario no describe el runtime actual. El [tablero](../../ROADMAP.md#documentexportservices) ordena EXPORT-002 a EXPORT-008; [BASELINE.json](docs/BASELINE.json) conserva la evidencia acotada.

## Mapa del componente

| Ubicación | Responsabilidad actual |
| --- | --- |
| `app/main.py`, `app/config/` | Factory, lifespan, configuración, CORS, readiness y JWT |
| `app/interfaces/api/v1/` | Siete rutas, esquemas y dependencias |
| `app/application/use_cases/manage_exports.py` | Nombre/ruta, renderizado, persistencia y descarga |
| `app/infrastructure/pdf/chat_pdf_renderer.py` | ReportLab/Platypus, texto, tabla y metadata |
| `app/infrastructure/database/` | SQLAlchemy y repositorio filtrado por dueño |
| [Esquema](../../scripts/database/schemas/009_exports.sql), [índices](../../scripts/database/indexes/001_indexes.sql), [triggers](../../scripts/database/triggers/001_updated_at_triggers.sql) | `document_exports`, referencias e índices |
| [Compose](../../docker/compose/export.yml) | Puerto 8016, montaje de archivos y clave pública de Auth |
| [Cliente web](../../frontend/src/features/document-export/api/document-export.api.js), [ChatPage](../../frontend/src/pages/ChatPage/ChatPage.jsx) | POST, descarga blob, enlace temporal y estado de exportación |
| [Sonda integral](../../scripts/smoke_documental.ps1) | Creación y descarga de un PDF sintético dentro del recorrido documental |

`tests/` contiene la suite mantenida y AGENTS las reglas del componente. Runtime, test y audit usan etapas separadas; pytest, Ruff, httpx, pypdf y pip-audit quedan fuera del runtime. `docs/` contiene evidencia documental; los PDFs y claves de diagnóstico permanecen temporales fuera de Git.

## Contrato actual

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| GET | `/api/v1/health` | Público; liveness sin comprobar DB/clave/storage |
| GET | `/api/v1/health/db` | Público; comprueba DB, clave RSA y escritura temporal en storage; 503 genérico ante fallo |
| POST | `/api/v1/exports/chat-message/pdf` | Renderiza de forma síncrona, guarda metadatos y devuelve ExportResponse (200) |
| GET | `/api/v1/exports` | Array completo del dueño, filtro `source_type` opcional, sin paginación |
| GET | `/api/v1/exports/{export_id}` | Metadatos propios o 404 |
| GET | `/api/v1/exports/{export_id}/status` | Misma consulta/DTO; no comprueba existencia ni integridad del archivo |
| GET | `/api/v1/exports/{export_id}/download` | FileResponse de la ruta persistida, después del filtro por dueño |

Las rutas funcionales verifican firma JWT y `token_type=access`. No exigen presencia de exp/iat/jti/huella ni identidad canónica, y no consultan cuenta activa o revocación por contraseña. El dueño se obtiene mediante fallback `user_id -> sub -> username -> unknown`; el repositorio lo filtra en lectura/listado y lo fija al insertar. No hay bypass administrativo explícito en ese repositorio. Una firma válida sigue siendo necesaria: aceptar claims incompletos en la sonda no demuestra falsificación de firmas ni que Auth real emita esos tokens.

El request permite `conversation_id`, `message_id`, `title`, `question`, `answer`, `sources` y `metadata`. Solo `answer` tiene `min_length=1`; el caso de uso rechaza respuesta en blanco. No hay cotas máximas HTTP/campos/fuentes/metadata ni restricción de campos superiores desconocidos. `sources` son diccionarios libres. El DTO devuelve IDs, título, formato/estado, filename, MIME, tamaño, metadata, URL relativa y timestamps; no devuelve `storage_path` ni dueño.

Los IDs de conversación/mensaje son referencias aportadas por el cliente. Las FK actuales comprueban existencia y usan SET NULL al borrar; no validan por sí solas dueño ni que ambos IDs correspondan entre sí. No se lee el contenido de otra conversación por recibir un ID: el problema observado por lectura es asociación/integridad, pendiente de pruebas reales PostgreSQL en EXPORT-003. Las fuentes impresas tampoco certifican origen documental o permisos vigentes. La sonda Node del adaptador confirmó POST/normalización/descarga blob y que conserva content/score pero descarta page y snippet, aunque estén en la entrada; EXPORT-004/006 deben acordar esos campos con sus consumidores.

## Flujo de persistencia y operación

El caso de uso sanea el título a slug ASCII de hasta 56 caracteres y añade diez hex de UUID. Resuelve y comprueba la ruta de creación respecto de la base. El renderer crea directorios y escribe directamente el PDF final; **después** el repositorio inserta, hace commit y refresh. No hay archivo temporal/exclusivo, compensación ante fallo de DB, protocolo de recuperación, cuotas ni retención. Solo se persiste COMPLETED en esta ruta; `error_message` no registra esos fallos. La descarga comprueba que la ruta persistida existe, sin volver a confinarla ni rechazar enlaces/archivos especiales. Una ruta alterada en DB no equivale a traversal controlado directamente por `export_id`.

La factory recibe Settings o variables de proceso, sin leer dotenv ni conectar/crear directorios al importar. DB y rutas absolutas de clave/storage son obligatorias. Lifespan comprueba clave pública RSA de al menos 2048 bits, consulta la tabla y prueba escritura temporal; prepara la base configurada y cierra el engine en finally incluso ante fallo. El pool aplica tamaño base, máximo total, espera de conexión y statement_timeout, con parámetros SQL ocultos. La clave se vuelve a leer para evitar caché obsoleto. Solo se rechaza el enlace directo en la base; confinamiento completo y ancestros siguen en EXPORT-005.

Compose usa variables explícitas, CORS local acotado y healthcheck de readiness. Los errores AppError, SQL, integridad y validación HTTP devuelven mensajes saneados sin valores de entrada ni rutas internas. Esto no compensa archivos huérfanos ni estados obsoletos. El runtime aún ejecuta como root y Compose usa el rol postgres de desarrollo hasta EXPORT-007. No montar ni limpiar `documents/exports` para ensayar fallos.

## Evidencia de EXPORT-002

49 pruebas locales sin PostgreSQL cubren configuración, import/factory, CORS, errores, claves, lifecycle y reemplazo de clave. Ocho pruebas adicionales PostgreSQL cubren creación/descarga, aislamiento por dueño, OpenAPI, fallos de escritura, pérdida de dependencias, pool/rollback y statement_timeout real. Usan claves efímeras, almacenamiento temporal, rollback y comprobación de ausencia de filas del dueño sintético. Los JWT se firman en pruebas; no se emiten por Auth real. Identidad vigente y referencias continúan en EXPORT-003.

Ruff y Compose config aprobados localmente. pip-audit 2.10.1 no encuentra avisos en los 33 paquetes del runtime resuelto para Windows, sin supresiones; los 46 avisos de la base histórica ya no describen este inventario. Esto no audita imagen Linux, SO ni vendorizados: EXPORT-007 y PLAT-002 mantienen ese alcance. El motor Docker local no estuvo disponible; imagen, PostgreSQL, arranque y reinicio se validan en el job `auth-db-roles` de CI.

## Evidencia de EXPORT-001

Se revisaron los 33 archivos Python de `app/` mediante lectura/AST, además de SQL, Compose/Dockerfile y consumidores. Las sondas usaron el Python 3.12.14 confiable incluido en el entorno, dependencias declaradas instaladas en destinos temporales y una clave RS256 efímera. Se desactivó lectura dotenv en la sonda, se usó un repositorio de prueba y TestClient sin lifespan; **no hubo PostgreSQL, Auth real ni contenedor Export en ejecución** porque el motor Docker local no responde. No confundir estos resultados con una suite de integración.

| Caso sintético | Resultado observado | Trabajo |
| --- | --- | --- |
| Sin Authorization / tipo refresh | 401 / 401 | Conservar |
| JWT firmado sin exp ni identidad; JWT con ID booleano | 200 en listado con repositorio sustituido | EXPORT-003 |
| Preflight desde origen externo | Allow-Origin `*` | EXPORT-002 |
| `answer` de un millón de caracteres | El esquema lo acepta; no se renderizó ese volumen | EXPORT-004 |
| Campo superior desconocido | Se ignora | EXPORT-004 |
| Creación pequeña y descarga | PDF de una página; 200 | Mantener contrato básico |
| Fichero ausente tras una creación | Status sigue COMPLETED; descarga 404 | EXPORT-005 |
| Excepción del repositorio tras render | 500 y un PDF huérfano en storage temporal | EXPORT-005 |
| Base de storage ocupada por un archivo sintético | 500 y nombre/ruta del error reflejados en detail | EXPORT-002/005 |
| Registro sintético con storage_path fuera de la base | Se devuelve ese archivo de prueba | EXPORT-005; requiere ruta persistida alterada |
| Otro dueño con repositorio sustituido | 404; SQL real leído contiene filtro owner | Integración real pendiente EXPORT-003 |

Dos muestras de una página se renderizaron completas con Poppler y se inspeccionaron visualmente. La muestra normal imprime entidades como `&amp;` en celdas, porque se escapan strings que Table trata como texto, no Paragraph. La muestra Unicode pierde caracteres y sus celdas extensas se solapan. Pypdf detectó glifos de sustitución; Poppler también advirtió fuentes de display ausentes en el entorno local. Se requiere repetir la revisión con fuentes embebidas y en la imagen final; no extrapolar la apariencia de este visor a todos los lectores.

La auditoría con pip-audit 2.10.1 del inventario resuelto para Windows encontró **46 avisos en cinco paquetes**:

| Paquete | Versión declarada/resuelta | Avisos |
| --- | --- | --- |
| PyJWT | 2.12.1 | 19 |
| cryptography | 46.0.6 | 9 |
| pytest | 8.3.5 | 2 |
| python-dotenv | 1.1.0 | 2 |
| Starlette | 0.46.2 | 14 |

Un aviso de PyJWT no indica fix en la base consultada. Son avisos del escáner, no 46 CVE únicos ni explotación validada. El inventario incluye herramientas hoy instaladas por requirements; excluye SO Linux, pip/base y copias vendorizadas de la imagen Docker. No se atribuye a esa imagen este conteo. Las versiones corregidas por aviso y el inventario se conservan en [BASELINE.json](docs/BASELINE.json); EXPORT-002 debe resolver el conjunto compatible y documentar cualquier residual.

Esta sección conserva resultados anteriores a EXPORT-002, incluidos errores de configuración ya corregidos. Para nuevos ensayos usa configuración sintética explícita, almacenamiento temporal y clave efímera. No reproducir comportamientos inseguros como garantías de la suite actual.

## Decisiones y mejoras por incrementos

1. **EXPORT-002:** factory/configuración explícita, CORS acotado, readiness y errores saneados, pool/timeouts efectivos, dependencias corregidas y suite PostgreSQL; runtime/test/audit separados. Primer incremento con comportamiento revisable sin cambiar el significado de las exportaciones.
2. **EXPORT-003:** identidad vigente de Auth y dueño canónico, incluso con roles administrativos; referencias opcionales válidas y coherentes. Mantener el concepto de instantánea enviada por cliente, sin atribuirle certificación de origen ni descargar recursos externos. Verificar con DB y tokens reales antes de cambiar contratos de referencias.
3. **EXPORT-004:** entradas y recursos acotados; fuentes tipadas, metadata finita, texto vacío/Unicode controlado, tablas con wrapping y repetición de encabezado, fuentes embebidas con licencia verificable. Definir texto plano/Markdown admitido y revisar PDFs multipágina con Poppler, sin HTML activo ni fetch remoto.
4. **EXPORT-005:** decidir almacenamiento tras medir límites: bytes acotados en PostgreSQL pueden evitar doble commit para PDFs pequeños; si se conserva storage privado, debe tener escritura exclusiva/atómica, estados y recuperación idempotente, confinamiento por descriptores y limpieza revisada. Medir capacidad/retención y planificar migración de filas y archivos sin atribuir dueño por nombre ni borrar fuentes automáticamente. Cubrir fallos/crash, concurrencia, archivos ausentes y rutas alteradas.
5. **EXPORT-006:** historial paginado con orden estable, DTO/estado de descarga coherente y consumidor web coordinado. Cancelación y respuestas tardías por sesión/tenant, doble envío, expiración, fallo de descarga, MIME/filename y liberación de object URLs; no generar enlaces de otra sesión.
6. **EXPORT-007:** rol PostgreSQL mínimo, helpers de referencia/identidad acotados, runtime sin root, storage/temporales privados y límites operativos según decisión de EXPORT-005. Build limpio, permisos reales, auditoría Python/SO/vendorizados con digest y disposición de avisos.
7. **EXPORT-008:** instalación limpia/actualización y recorrido con dos usuarios reales, fallos/recuperación y web, revisión de archivos y documentación final. Retirar este diagnóstico al sustituirlo por operación final, mantener seguimientos y cerrar al integrar el PR; después DRIVE-001.

Las referencias de conversación/mensaje se validarán antes de asociar metadatos; eso no convierte el contenido suministrado en una copia certificada del historial. Cualquier futura exportación canónica desde servidor requeriría revisar sincronización del chat y permisos documentales como un contrato distinto. El historial y la capacidad deben acotarse antes de una publicación pública, con conservación de datos heredados y decisiones de retención explícitas.

## Fuentes técnicas y límites

- [PyJWT: opciones de decode](https://pyjwt.readthedocs.io/en/stable/api.html): exigir presencia y validar tipos/valores son comprobaciones diferentes. La versión de documentación consultada es 2.15.1; la conducta de 2.12.1 se midió localmente.
- [FastAPI: lifespan](https://fastapi.tiangolo.com/advanced/events/): inicialización/cierre deben mantenerse dentro de un ciclo de vida explícito y verificable.
- [ReportLab: Tables](https://docs.reportlab.com/reportlab/userguide/ch7_tables/): celdas con Paragraph/Flowables permiten componer contenido con wrapping; se debe verificar la versión elegida con pruebas.
- [PostgreSQL 16: constraints](https://www.postgresql.org/docs/16/ddl-constraints.html): una FK simple no expresa por sí sola la relación de dueño/coherencia propuesta para estos metadatos.

Las conclusiones combinan lectura, sondas sintéticas y documentación primaria. No constituyen un escaneo exhaustivo de seguridad ni validación de cada advisory. El análisis histórico no validó arranque/salud reales, aislamiento PostgreSQL, JWT reales ni concurrencia entre conexiones; EXPORT-002 incorpora la suite PostgreSQL y EXPORT-003 completa Auth vigente y concurrencia; no se declara cerrado Export por haber terminado el análisis.

## Ejecución actual

El entrypoint es `uvicorn app.main:create_app --factory --port 8016` desde este directorio; ya no existe `app.main:app`. El proceso requiere `DATABASE_URL` (postgresql+psycopg), `AUTH_JWT_PUBLIC_KEY_PATH` y `EXPORT_STORAGE_BASE_PATH` absolutos. `PGPASSWORD` permite separar la contraseña de la URL. La base debe contener el esquema documental antes del arranque; el servicio no migra tablas ni lee dotenv.

`CORS_ORIGINS` es un array JSON de orígenes HTTP(S) explícitos sin rutas/credenciales/comodines; por defecto localhost y 127.0.0.1:3000, `[]` deshabilita acceso cruzado. `AUTH_JWT_ALGORITHM` solo admite RS256. `DB_POOL_MIN_SIZE`/`MAX_SIZE` son 1/10 (1..100, mínimo <= máximo); `DB_TIMEOUT_SECONDS` es 30 (1..300), aplicado a conexión, espera de pool y sentencias. `LOG_LEVEL` admite DEBUG/INFO/WARNING/ERROR/CRITICAL. Compose permite ajustar orígenes y pool mediante `EXPORT_CORS_ORIGINS`, `EXPORT_DB_POOL_MIN_SIZE`, `EXPORT_DB_POOL_MAX_SIZE` y `EXPORT_DB_TIMEOUT_SECONDS`; no inyecta el env_file global.

Desde la raíz:

```powershell
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait document-export-service
```

El segundo comando monta los exports existentes; úsalo solo como operación autorizada de esa instalación. CI arranca desde checkout vacío y comprueba reinicio saludable. Para probar, aprovisiona el esquema en una base sintética y ejecuta:

```powershell
docker compose -f docker/docker-compose.yml run --build --rm --no-deps export-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps export-tests ruff check --no-cache app tests
docker compose -f docker/docker-compose.yml run --build --rm --no-deps export-audit
```

Los targets de prueba no montan el almacenamiento operativo. Fuera de Compose instala requirements.txt y requirements-test.txt en un entorno aislado; `python -m pytest -q -p no:cacheprovider -m "not postgres" tests` ejecuta las 49 pruebas independientes de DB. La suite completa requiere `EXPORT_TEST_DATABASE_URL` explícita, credencial de proceso y esquema sintético; sin ella las pruebas PostgreSQL fallan, no se omiten silenciosamente. No usar una base personal/compartida. El audit target congela el runtime antes de instalar pip-audit y analiza ese inventario separado de las herramientas.

## Licencia

Aplican los términos del [LICENSE del repositorio](../../LICENSE). No se incorporaron fuentes de terceros ni PDFs de prueba al repositorio.
