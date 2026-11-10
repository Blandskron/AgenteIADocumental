# Auditoría de cierre — 10 de noviembre de 2026

**Veredicto: NO está listo para la versión 1.0 Open Source solicitada.** El flujo documental existe; faltan cerrar autorización RAG, bootstrap sin intervención, configuración segura y validación de instalación. La licencia sigue reservando todos los derechos. No hace falta ampliar funcionalidades ni cambiar de arquitectura.

Auditoría de solo lectura del producto: no se modificaron código, Compose, esquemas, datos, licencia ni referencias Git. Este informe es el único archivo de entrega añadido. Revisión dirigida de contratos, once servicios, Dockerfiles, configuración, inicialización, migraciones, autorización, pruebas y CI; no constituye una revisión línea por línea de todo el repositorio ni certifica ausencia de vulnerabilidades.

Base: `1235d985b0237b4e2ea82cad3d9f79844d777378`, rama `codex/close-portfolio-roadmap`, árbol inicialmente limpio y mismo contenido que `origin/main` local. La rama `main` local está atrasada; no se cambió de rama. Las consultas al conector GitHub no devolvieron issues ni PR abiertos. Repositorio público confirmado. No se crearon issues, PR, commits, tags ni releases.

## A. Estado actual

| Estado | Componente y evidencia | Conclusión |
| --- | --- | --- |
| Implementado y verificado ahora | `docker/docker-compose.yml` y ocho archivos de `docker/compose/`, incluido `verification.yml` | Las dos configuraciones resuelven con `.env.example`; validación estática, sin arrancar contenedores. |
| Implementado y verificado ahora | `frontend/package.json`, `tests/`, `tests/browser/` | Instalación npm, 123 pruebas Node, 21 escenarios Chromium, build y auditoría npm aprobados. Navegador con APIs simuladas. |
| Implementado; evidencia integral anterior, no repetida ahora | `docs/release/VERIFICATION.json` | 78 etapas con código 0, finalizadas `2026-11-10T00:34:25.131Z` (9 de noviembre en Chile), sobre commit `3b57b25…`: roles, suites, carreras SQL y recorrido HTTP. No atribuir esos resultados a una ejecución de esta auditoría. |
| Implementado; pendiente de ejecución actual | `scripts/database/run_all.sql`, `extensions/001_extensions.sql`, `docker/compose/auth.yml` | PostgreSQL/pgvector, esquema y migraciones están orquestados. Cadena: DB saludable → esquema → roles Auth → migraciones Django/concesiones → integridad 006 → Auth HTTP. |
| Implementado; pendiente de ejecución actual | `backend/AuthServices/core/jwt_keys.py`, `entrypoint.sh`, `core/test_jwt_keys.py` | RSA generado automáticamente; publicación atómica, privada 0600 y pública 0644. Volúmenes separados; consumidores solo montan pública en lectura. No se justifica otro gestor de claves para la demo local. |
| Parcial frente al objetivo nuevo | `backend/AuthServices/README.md`, `users/management/commands/`, `docker/compose/auth.yml` | Existe alta manual `createsuperuser`; no existe comando de bootstrap ni credenciales iniciales conectadas a Compose. No hay contraseña universal del administrador Django en el arranque actual. |
| Implementado; autorización incompleta | Chat, Embedding, Search, Access, Library, Transfer, Conversation | Hay filtros documentales, roles DB y suites. Las diferencias de tenant y revocación descritas en C impiden considerarlos uniformemente seguros. |
| Implementado; evidencia anterior | `DocumentExportServices`, `ProfileServices`, `GoogleDriveImportServices` | Identidad vigente mediante helpers SQL, roles mínimos y pruebas. PDF guarda una instantánea del cliente; no certifica la respuesta ni su contenido. Drive permanece deshabilitado y no es requisito. |
| Obsoleto | `ROADMAP.md` eliminado en `1235d98`; versión anterior inspeccionada con `git show 9b39a64:ROADMAP.md` | Cerraba el portafolio y sus tarjetas. No hay backlog vigente que obligue a implementar OCR avanzado, agentes o nuevas integraciones. No reabrir tarjetas históricas por sus títulos. |

El núcleo necesario es PostgreSQL/pgvector, Auth, Embedding, Search/Access, Chat, Export y frontend. Conversation sostiene el historial actual; Library, Transfer y Profile tienen consumidores reales en la web y deben conservarse. Los jobs SQL son inicializadores necesarios, no servicios duplicados. Drive es opcional funcionalmente, aunque frontend depende de su health incluso deshabilitado. `pgadmin` es una herramienta operativa sin responsabilidad en el recorrido principal.

## B. Diferencias frente a la instalación ideal

1. Después de Compose todavía hay que ejecutar `createsuperuser` manualmente.
2. En Linux hay que preparar el propietario de `documents` y coordinar UID/GID de ingesta y acceso. El bind mount oculta los permisos preparados en la imagen; un directorio nuevo creado por Docker puede quedar inaccesible para UID 10004.
3. El `.env` raíz no controla todas las credenciales: PostgreSQL y los jobs usan una contraseña fija; Auth carga también su propio `.env.example`. Copiar y editar únicamente el ejemplo raíz no resuelve esos secretos.
4. `up --wait` comprueba salud de servicios, no una respuesta real de IA. Se necesita conectividad para imágenes/paquetes, descarga inicial de E5 y Groq con clave válida. E5 tiene revisión fijada y usa CPU/Safetensors. Los adaptadores convierten fallos a errores controlados; el chat devuelve contingencia sin fuentes cuando falla la IA. Esa contingencia no acredita RAG exitoso.
5. No se pudo demostrar aquí el arranque limpio: Docker CLI está disponible, pero falta el motor `dockerDesktopLinuxEngine`. No es un fallo demostrado del código.

## C. Hallazgos priorizados

P0 se usa para instalación/funcionalidad/confidencialidad bloqueante; P1 para cierre confiable y requisitos de publicación. Un requisito legal P1 también impide anunciar Open Source.

| ID | Problema y evidencia | Impacto / prioridad | Solución mínima | Criterio de aceptación |
| --- | --- | --- | --- | --- |
| C01 | RAG autoriza `owner_groups` sin comprobar tenant. `RagDocumentChatServices/app/infrastructure/database/repositories/vector_repository_pgvector.py:90–115`; búsqueda sí combina grupo y tenant en `DocumentSearchServices/.../document_search_repository_pg.py::_apply_access_filter`. Ingesta estampa esos grupos globales en `config/security.py::build_document_access_metadata`. | Un usuario con grupo Django común y permiso de chat puede recuperar fragmentos de otra empresa por esa rama OR. Afecta búsqueda vectorial y resumen. **P0**, demostrado por inspección; falta reproducción SQL. | Alinear el predicado RAG con el contrato de búsqueda/acceso, incluyendo tenant y precedencia de columnas canónicas frente a metadata heredada. No quitar autorizaciones legítimas de dueño/asignación. | Dos empresas, mismo grupo, usuario sin membresía ajena: ni pregunta ni resumen devuelven fuentes ajenas ni las envían al proveedor. Caso positivo autorizado conserva acceso. |
| C02 | Bootstrap del administrador ausente. `docker/compose/auth.yml::auth-migrate` solo ejecuta migrate/grant; README exige comando interactivo. | El flujo clon → Compose → login no termina automáticamente. **P0** del objetivo de instalación. | Un management command y un job Compose posterior a migraciones/integridad, sin DDL ni claves de firma. Credenciales iniciales explícitas. | Primera creación segura; cuenta existente intacta; contraseña cambiada por el usuario no se resetea; configuración inválida falla claramente; dos ejecuciones concurrentes no duplican ni escalan una cuenta existente. Login real desde web. |
| C03 | Bind mount `../../documents` con usuario 10004; `docker/compose/documents.yml`, Dockerfile de ingesta y README raíz. | Clon limpio Linux puede no escribir documentos y falla readiness. **P0** para instalación sin pasos posteriores; no reproducido aquí. | Volumen dedicado inicializado con propietario correcto, o preparación acotada del directorio. Conservar ruta/datos de instalaciones existentes; no `chown -R` indiscriminado. | Clon Linux sin directorio previo: upload/download/borrado funcionan. Reinicio conserva documentos. Instalación anterior conserva almacenamiento. |
| C04 | PostgreSQL y pgAdmin usan contraseña pública fija; varios jobs repiten `PGPASSWORD`; Auth tiene otro ejemplo. `docker/compose/infra.yml`, `auth.yml`, `.env.example`, `backend/AuthServices/.env.example`. | No cumple el requisito de credenciales administrativas propias. Exposición limitada a loopback, no evidencia de explotación remota. **P1**, necesario antes de publicar esta instalación. | Parámetros obligatorios coherentes desde `.env` para administrador DB; retirar contraseña fija de arranque. pgAdmin solo en perfil opcional con credenciales propias. No generar doce secretos adicionales manuales si pueden aprovisionarse de forma local segura. | Configuración ausente falla antes de arrancar; ejemplo sin contraseña administrativa utilizable; todos los jobs conectan; reiniciar no rota a ciegas credenciales de una DB existente. |
| C05 | Siete servicios validan firma/expiración/tipo, pero no cuenta activa/huella actual: `app/config/security.py` en Chat, Embedding, Search, Access, Library, Transfer y Conversation. Claims de rol/membresía provienen del JWT. Auth fija access a 10 minutos. | Deshabilitar cuenta, cambiar contraseña o retirar rol no invalida inmediatamente ese acceso; un token de superadmin conserva bypass hasta expirar. **P1**, estático; falta reproducción HTTP. | Reutilizar comprobación acotada de identidad vigente y autorización actual, con permisos mínimos. Perfil/Export/Drive ya muestran un patrón local; no añadir microservicio. | Token emitido antes de baja/cambio/retirada pierde las operaciones correspondientes; fallo DB cierra acceso con error controlado. Probar cada consumidor afectado. |
| C06 | No hay prueba actual completa ni bootstrap/reinicio en el arnés principal. `scripts/release/demo_flow.py` inserta usuarios sintéticos directamente por SQL; `verify.mjs` no demuestra conservación de contraseña tras reiniciar. | Los 78 checks anteriores no cubren toda la aceptación nueva. **P1**, puerta de validación; Docker ausente es limitación del entorno. | Extender el arnés existente con instalación normal y bootstrap, reinicio y persistencia; mantener simulación explícita y añadir una comprobación separada de Groq real. | Los 17 pasos de F pasan en proyecto aislado, con IDs/contraseña preservados y cero duplicados. Nueva evidencia identifica commit e imágenes. |
| C07 | `LICENSE` reserva derechos. No se encontraron `CONTRIBUTING.md` ni `SECURITY.md`; no hay tags locales. | Falta preparación mínima para la publicación Open Source. **P1**, bloqueante de esa publicación. No se verificó catálogo remoto de releases. | Confirmar derechos con propietario; elegir licencia mediante aprobación expresa; conservar atribuciones; guía breve de contribución/reporte privado y release versionada cuando proceda. | Titular aprueba licencia y procedencia; avisos incluidos; documentación vigente; versión/tag/release corresponden al commit validado. No publicar automáticamente. |
| C08 | `pgadmin` arranca sin perfil y publica 5050; README de Profile conserva seguimientos que la evidencia central declara integrados; `.env.example` dice que el rol Export sigue pendiente. | Complejidad y documentación contradictoria. **P1** para corregir instrucciones; cambios cosméticos **P2**. | Perfil opcional para pgAdmin y edición puntual de instrucciones afectadas. Mantener servicios usados por la interfaz. | Arranque normal no levanta pgAdmin; no hay instrucciones contradictorias sobre requisitos o cierre. |

Revisión de seguridad adicional: los puertos publicados de Compose se limitan a `127.0.0.1`; los CORS efectivos de Compose usan los dos orígenes locales. El `CORS_ORIGINS=["*"]` del ejemplo raíz no representa el CORS efectivo de estos contenedores y debe aclararse para ejecución directa. No se propone exponerlos públicamente.

No aparecieron coincidencias en los 192 commits alcanzables por referencias locales para patrones de claves Groq/Google/AWS y bloques de clave privada; tampoco rutas históricas `.env`, PEM o JSON de credenciales en las búsquedas realizadas. Es una búsqueda limitada por patrones y referencias disponibles, sin escáner de entropía ni comprobación de referencias borradas/remotas. No prueba ausencia absoluta de secretos. Los ejemplos contienen secretos públicos de desarrollo, tratados en C04; no se usó el `.env` personal.

`IMAGE_AUDIT.json` conserva doce imágenes, once inventarios Python y disposición individual: diez backends con 47 coincidencias HIGH/11 CVE de SO y la ingesta con 49/13; frontend sin esas coincidencias. Son resultados fechados, no vulnerabilidades explotables recién verificadas. No se reconstruyeron ni reescanearon imágenes ahora. `npm audit` sí se consultó de nuevo y dio cero avisos; no sustituye la auditoría Python/SO.

Procedencia: el historial local atribuye commits a Blandskron/Bastian Landskron; eso no demuestra por sí solo titularidad completa. Noto Sans incluye SIL OFL y hashes; el Dockerfile conserva licencias de Tesseract/datos de idioma; Lucide declara ISC. Falta confirmar derechos del conjunto y avisos de distribución antes de cambiar LICENSE. No se detectó una incompatibilidad concreta que justifique sustituir recursos.

## D. Funcionalidades innecesarias para 1.0

| Propuesta | Decisión |
| --- | --- |
| OCR avanzado | **P2**. Conservar extractores y OCR nativo existentes; no ampliarlos. |
| Comparación semántica | **P2**. No necesaria para carga/pregunta/PDF. |
| Knowledge Graph | **DESCARTAR del cierre**. Ningún requisito actual lo necesita. |
| MCP y SDK Python | **P2**. No necesarios para la interfaz actual. |
| Workflows y agentes autónomos | **DESCARTAR del cierre**. Sin relación con fallos demostrados. |
| Arquitectura multimodelo | **P2**. Mantener E5 y Groq actuales. |
| Conectores nuevos y OAuth Drive real | **P2**. Drive ya puede permanecer deshabilitado. |
| Observabilidad avanzada | **P2**. Usar healthchecks y logs actuales para el alcance local. |
| Nuevos microservicios, Kubernetes, cambio de frameworks | **DESCARTAR** como solución al cierre. |

## E. Plan de cierre: tres bloques

1. **Correcciones bloqueantes:** C01 y C05 con regresiones de autorización; C04 con configuración propia y sin credenciales universales. Conservar arquitectura, formatos y migraciones existentes.
2. **Instalación y bootstrap automático:** C02/C03 y pgAdmin opcional. Basta un comando Django, no un subsistema nuevo: transacción y bloqueo asesor PostgreSQL común entre ejecuciones; buscar cuenta existente antes de crear; no cambiar contraseña/flags de existentes ni promover un username ocupado. Si no hay superusuario y el nombre está ocupado por otra cuenta, fallar claramente. Si ya existe administrador, conservarlo. Validar las credenciales para creación con validadores Django, sin incluir sus valores en errores/logs. Ejecutar después de `tenant-integrity`, con rol DML suficiente y sin privilegios de migración, sin montar firma JWT; Auth HTTP depende de su éxito. Entregar un README y ejemplo raíz coherentes.
3. **Validación final y preparación Open Source:** C06–C08; ejecutar matriz completa en Linux y Windows soportados sin tocar instalaciones propias, reconstruir/reevaluar imágenes y registrar límites. Resolver licencia/procedencia con el propietario y preparar la versión revisable. Integrar/publicar solo según la autorización específica de esa fase.

## F. Pruebas y veredicto final

Ejecutado en esta auditoría:

| Comprobación | Resultado |
| --- | --- |
| Estado Git, rama, historial y diferencias con `origin/main` local | Árbol inicialmente limpio; contenido equivalente. Sin cambiar referencias. |
| Compose normal con `--env-file .env.example ... config --quiet` | **APROBADO**, exit 0. |
| Compose `bd-final-check` con `verification.yml` y ejemplo | **APROBADO**, exit 0. |
| `npm ci` | **APROBADO**, 23 paquetes instalados. Los primeros intentos en sandbox fallaron con `Exit handler never called`; repetición fuera de sandbox aprobada. |
| `npm test` | **APROBADO**, 123/123, cero omitidos. |
| `npm run build` | **APROBADO**, avisos de directiva `use client` de Lucide, sin error de compilación. |
| `npm audit --audit-level=low` | **APROBADO**, cero avisos reportados al consultar el registro. |
| `npm run test:browser` | **APROBADO**, 21/21 en 19,1 segundos. Primer intento en sandbox interrumpido al no progresar; repetición fuera de sandbox aprobada. APIs simuladas, no login contra el stack. |
| `docker ... bd-final-check ... up -d --build --wait blandskron-frontend` | **NO EJECUTABLE**: motor Docker Linux ausente; salida 1 antes del arranque. No se crearon volúmenes ni se borraron datos. |
| Suites Python/SQL y nuevo escaneo de imágenes | **NO EJECUTADOS**: sin motor Docker; `python` local apunta a alias WindowsApps no ejecutable. |

Matriz de aceptación pedida (ningún paso de servicios se marca aprobado ahora):

| Pasos | Estado de esta ejecución |
| --- | --- |
| 1. Clon limpio | No se creó un clon separado; se auditó el checkout limpio identificado. |
| 2–3. Crear `.env` y configurar mínimos | Se utilizó `.env.example` explícitamente; no se creó ni leyó `.env` personal. El procedimiento mínimo nuevo todavía falta. |
| 4–6. Compose, esquema/migraciones y administrador automático | Arranque bloqueado por motor ausente; automatización del administrador no implementada. |
| 7. Login real desde frontend | Pendiente con bootstrap y stack reales; navegador con APIs simuladas no lo sustituye. |
| 8–12. Upload sintético, embeddings, búsqueda, RAG con fuentes y PDF | Pendientes ahora. Existe evidencia anterior con E5/PDF reales y Groq simulado. Groq vivo no se verificó en esta sesión. |
| 13–16. Reinicio, persistencia, contraseña intacta y segundo arranque | Pendientes; añadir verificación explícita al arnés después del bootstrap. |
| 17. Segundo usuario sin acceso | Pendiente de repetición y ampliación para grupo común entre tenants, roles retirados y cuenta deshabilitada. |

**¿Listo para lanzarse? NO.** Bloqueantes técnicos: aislamiento RAG, bootstrap y permisos automáticos del almacenamiento Linux. Cerrar también configuración administrativa, revocación, evidencia de instalación y preparación legal antes de anunciar la versión solicitada. No se demostró un fallo de generación de embeddings, PDF o del orden de migraciones que justifique reescribirlos.

**Conjunto mínimo de cambios:** corregir los controles de acceso identificados; añadir un comando/job de administrador; preparar almacenamiento; centralizar credenciales necesarias; hacer pgAdmin opcional; extender las pruebas existentes; corregir documentación puntual y completar la decisión de licencia/versión. Todo lo enumerado en D puede esperar. Tras cumplir esta aceptación, detener el desarrollo funcional de 1.0 y recomendar publicación para el entorno local declarado.

La siguiente fase propuesta queda delimitada a esos tres bloques. Esta auditoría no implementa cambios de producción, no sustituye la licencia y no autoriza publicación ni escritura directa en main.
