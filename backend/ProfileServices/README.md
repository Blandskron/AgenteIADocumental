# ProfileServices

Servicio FastAPI de perfil y avatar de Blandskron Documental, publicado localmente en `http://localhost:8015`. AuthServices administra identidad, credenciales y membresías; Profile guarda datos de contacto y presentación en `user_profiles` y archivos en `uploads/profile`.

**Estado:** PROFILE-001 y PROFILE-002 integrados en PR #59/#60. PROFILE-003 valida la identidad vigente y limita los datos del perfil a su dueño; retira las rutas globales y por ID. Los límites/consistencia de escritura y el ciclo privado del avatar siguen en PROFILE-004 a PROFILE-006; el rol DB acotado y usuario de contenedor en PROFILE-007. El [diagnóstico histórico](#diagnóstico-profile-001) describe la línea base, no las garantías actuales. El estado vive en el [tablero](../../ROADMAP.md#profileservices).

## Mapa para trabajar

| Ubicación | Responsabilidad actual |
| --- | --- |
| `app/main.py` | Factory `create_app`, lifespan, CORS, excepciones y montaje público `/static` |
| `app/config/` | Settings, JWT, logging y sesión por petición |
| `app/interfaces/api/v1/` | Dos rutas de salud, tres operaciones propias, dependencias y esquemas |
| `app/application/use_cases/manage_profile.py` | Perfil propio vacío cuando no existe y actualización |
| `app/domain/entities.py` | Entidad de perfil |
| `app/infrastructure/database/` | SQLAlchemy, sesiones y repositorio PostgreSQL |
| [Esquema](../../scripts/database/schemas/008_profiles.sql) y [triggers](../../scripts/database/triggers/001_updated_at_triggers.sql) | PK generada, `user_id` único, metadata JSONB y `updated_at` |
| [Compose](../../docker/compose/profile.yml) | Puerto, clave pública de Auth y volumen de avatares |
| [Cliente web](../../frontend/src/features/profile/api/profile.api.js), [hook](../../frontend/src/features/profile/hooks/useProfile.js) y [página](../../frontend/src/pages/ProfilePage/ProfilePage.jsx) | Consulta/actualización propia, upload y cambio de contraseña vía Auth |
| [AuthProvider](../../frontend/src/app/providers/AuthProvider.jsx) y [Sidebar](../../frontend/src/widgets/Sidebar/Sidebar.jsx) | Perfil global y avatar |

`tests/` contiene la suite permanente y CI la ejecuta sobre PostgreSQL. Las etapas Docker `runtime`, `test` y `audit` separan las herramientas del servicio; el inventario auditado se captura antes de instalar pip-audit. No hay aplicación Django ni código Python dentro de una carpeta documental que sea necesario trasladar.

## Contrato actual

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| GET | `/api/v1/health` | Público; devuelve `status: ok`, sin comprobar dependencias |
| GET | `/api/v1/health/db` | Público; comprueba tablas de perfil/identidad, clave pública y escritura temporal en storage; 503 genérico si fallan |
| GET | `/api/v1/profile` | Perfil propio o entidad vacía con ID y timestamps nulos; consultar no inserta |
| PUT | `/api/v1/profile` | Crea o actualiza perfil propio |
| POST | `/api/v1/profile/upload` | JWT access; verifica imagen, guarda archivo y devuelve `{ "url": "..." }` |
| GET | `/static/{filename}` | Archivo público, sin JWT ni comprobación de propiedad |

Las tres operaciones requieren Bearer access RS256 y cuenta vigente. `user_id` debe ser un entero positivo dentro de int64 (no booleano, cadena ni decimal). Se exigen `exp`, `iat`, `jti`, `token_type` y `hash_password`; tiempos enteros válidos, `iat` no negativo y anterior a `exp`, `jti` no vacío de hasta 128 caracteres y tipo `access`. Un `sub` opcional debe ser la cadena decimal canónica del mismo ID; no hay fallback a `username`. Flags booleanos y listas de grupos/permisos/roles, si aparecen, deben tener tipos correctos. El contrato actual de Auth no emite issuer/audience; no se introducen valores inventados que rompan login.

Cada petición autenticada consulta si `public.auth_user` contiene ese ID activo y si `upper(md5(password))` coincide con `hash_password`, como `CHECK_REVOKE_TOKEN` de SimpleJWT en Auth. La expresión opera sobre la contraseña **ya codificada por Django** y reproduce su huella de revocación; no reemplaza el algoritmo de contraseña por MD5. La consulta devuelve solo un booleano, nunca la contraseña codificada. Una cuenta inexistente/inactiva/eliminada o contraseña cambiada devuelve 401 genérico con `WWW-Authenticate: Bearer`; un fallo de consulta devuelve 503 sin detalles internos.

El repositorio queda ligado al dueño autenticado al construirse: consultas y escrituras no reciben un ID de destino del cliente ni disponen de listado global. Ser superadmin, staff o administrador de tenant no amplía ese alcance. El chequeo de vigencia ocurre al autenticar la petición; no promete serializar una escritura frente a cambios simultáneos de Auth (consistencia/concurrencia en PROFILE-004 y PLAT-001).

**Transición de contrato:** se retiran `GET /api/v1/profiles`, `GET /api/v1/profiles/{user_id}` y `PUT /api/v1/profiles/{user_id}`. Devuelven 404 y no figuran en OpenAPI, incluso para el propio ID o administradores. La búsqueda de consumidores no encontró usos en la web; las integraciones externas deben usar `/api/v1/profile` con la sesión del dueño. Los tokens anteriores sin los claims requeridos se rechazan; renueva la sesión en Auth. No se migran ni borran perfiles históricos: registros asociados a username o IDs no canónicos requerirán inventario y reparación explícita en PROFILE-004.

PUT admite `email`, `phone_number`, `profile_picture_url` y `additional_info`. Los tres primeros son cadenas libres; la metadata es un objeto JSON libre. Los campos desconocidos se ignoran. En un registro existente, omitir un campo o enviar `null` conserva el valor; una cadena vacía sí lo reemplaza. La metadata enviada sustituye el objeto completo. Es una actualización parcial pese al verbo PUT.

La respuesta contiene `profile_id`, `user_id`, esos cuatro campos y `created_at`/`updated_at`. Añade `groups` y `permissions` del JWT validado para mostrar el contexto de la sesión; no son una nueva fuente de autorización ni se refrescan desde membresías en Profile. Cambios de permisos se reflejan al renovar el token en Auth. No se devuelven huella, contraseña, jti ni otros internos del token. Este email no actualiza `auth_user.email`, las credenciales ni los claims de Auth.

La revocación aquí cubre cambio de contraseña y estado/existencia de cuenta. El logout de Auth invalida el refresh; un access ya emitido puede seguir válido hasta su expiración (10 minutos según Auth), salvo cambio de contraseña o cuenta. No se afirma revocación instantánea de access por logout.

El upload exige la misma identidad vigente, genera un UUID y extensión según el formato detectado, sin reutilizar el nombre enviado. Verifica con `Image.verify()` y escribe los bytes originales. No asocia automáticamente la foto al perfil: la web recibe la URL y después guarda con PUT. `/static` continúa público hasta la transición coordinada de PROFILE-005: la privacidad del JSON de perfil no implica todavía privacidad del archivo. No hay inventario de propietario de archivo, reemplazo ni recolección de archivos abandonados.

## Arranque y configuración actuales

Desde la raíz, con `.env` local ya configurado:

```powershell
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait profile-service
```

Compose monta el directorio persistente `uploads/profile`. Las pruebas usan directorios temporales y rollback; la comprobación local de arranque de PROFILE-002 usó un volumen Docker sintético separado. No se necesita clave de IA/OAuth para Profile.

| Variable | Situación actual |
| --- | --- |
| `DATABASE_URL` | Obligatoria, driver `postgresql+psycopg`, host/usuario/base explícitos; sin default ni contraseña embebida en la aplicación |
| `PGPASSWORD` | Compose declara la contraseña de desarrollo de la infraestructura local; no se inyecta el `.env` global. El rol sigue siendo `postgres` hasta PROFILE-007 |
| `AUTH_JWT_PUBLIC_KEY_PATH` | Obligatoria y absoluta; Compose monta solo la clave pública en `/app/auth_keys/public.pem`; se exige RSA pública de al menos 2048 bits |
| `AUTH_JWT_ALGORITHM` | Solo `RS256` |
| `CORS_ORIGINS` | Lista JSON de orígenes HTTP(S) explícitos, sin comodines, rutas ni credenciales; default localhost/127.0.0.1:3000. `[]` deshabilita CORS |
| `PROFILE_UPLOADS_DIR` | Obligatoria y absoluta; misma configuración para upload, static y salud. Compose usa `/app/uploads` |
| `APP_ENV`, `APP_NAME`, `LOG_LEVEL` | Entorno, título y logging |
| `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_TIMEOUT_SECONDS` | Defaults 1/10/30; tamaños 1–100, min ≤ max, timeout 1–300 segundos. Pool retenido = min, overflow = max − min; no se preabren min conexiones |

Settings no lee archivos `.env`. Compose permite ajustar `PROFILE_CORS_ORIGINS`, `PROFILE_DB_POOL_MIN_SIZE`, `PROFILE_DB_POOL_MAX_SIZE` y `PROFILE_DB_TIMEOUT_SECONDS` mediante interpolación explícita; no transmite claves de IA/OAuth. Los errores de validación ocultan los valores de entrada y el repr de Settings excluye la URL DB.

El timeout se aplica a espera del pool, conexión y consultas PostgreSQL (`statement_timeout`). El engine usa pre-ping, oculta parámetros SQL, revierte sesiones con error y se libera aun si falla el arranque. La factory no crea archivos ni conexiones al importar; lifespan valida DB/tabla y clave, prepara storage y prueba escritura temporal que se elimina automáticamente. Una dependencia inválida aborta con un mensaje genérico. `/health` indica vida del proceso; `/health/db` vuelve a comprobar dependencias y es el healthcheck de Compose. La clave se relee para detectar pérdida/cambio posterior sin cache obsoleta.

La imagen de ejecución sigue como root sobre `python:3.12-slim`; el rol y los permisos finales se entregan en PROFILE-007. El upload aún no tiene el límite/canonización/privacidad de PROFILE-005. Configurar un directorio no implica haber completado su confinamiento ante todas las carreras de archivos.

Para ejecución fuera de Docker, declara `DATABASE_URL`, `AUTH_JWT_PUBLIC_KEY_PATH` y `PROFILE_UPLOADS_DIR` (rutas absolutas), instala `requirements.txt` en un entorno virtual y desde este directorio ejecuta `uvicorn app.main:create_app --factory --port 8015`. La contraseña de DB puede suministrarse por `PGPASSWORD`. No cargar un `.env` global dentro de la aplicación.

## Pruebas y auditoría

Desde la raíz, con PostgreSQL/esquema inicializados por Compose:

```powershell
docker compose -f docker/docker-compose.yml run --build --rm --no-deps profile-tests
docker compose -f docker/docker-compose.yml run --rm --no-deps profile-tests ruff check --no-cache app tests /profile-checks
docker compose -f docker/docker-compose.yml run --build --rm --no-deps profile-audit
docker compose -f docker/docker-compose.yml exec -T profile-service python -m pip check
```

La suite exige `PROFILE_TEST_DATABASE_URL` explícita, provista por el servicio `profile-tests`. No crea/migra tablas ni usa uploads reales. Las escrituras HTTP quedan dentro de savepoints y una transacción exterior; al terminar se comprueba desde otra conexión que no persiste el usuario sintético. Las pruebas de pool y statement timeout usan conexiones PostgreSQL reales. Los fallos de escritura por permisos se inyectan para que el resultado no dependa de ejecutar la suite como root.

El job `auth-db-roles` construye/arranca Profile, comprueba ausencia de herramientas de test/audit en runtime, ejecuta suite/Ruff/auditoría y verifica reinicio saludable. Después ejecuta el [contrato HTTP Auth–Profile](../../scripts/profile/verify_auth_contract.py) contra ambos servicios reales. El job Compose verifica la lista de variables explícitas. La concurrencia de escrituras, límites y privacidad de archivos permanecen en sus tarjetas.

PROFILE-002 actualiza FastAPI/Starlette, PyJWT, cryptography, python-dotenv, Pillow y python-multipart, conservando el resto del conjunto compatible. La auditoría consulta el inventario de runtime antes de instalar herramientas; no confundir ese resultado con un escaneo de SO o de copias vendorizadas (PROFILE-007). TestClient emite una advertencia sobre la futura migración de httpx a httpx2, limitada a la etapa de pruebas.

Evidencia local de PROFILE-002 (6 de noviembre de 2026): **52 pruebas aprobadas**, Ruff y pip check aprobados; `profile-audit` sin avisos conocidos, sin supresiones. Se construyeron las tres etapas con proyecto `library008-release`, se comprobó la lista de variables/CORS/montaje de clave/healthcheck y se validó arranque y reinicio contra PostgreSQL existente y clave pública real de Auth, con volumen sintético separado. Runtime no contiene pytest/Ruff/httpx/pip-audit. No se usaron avatares reales ni se ejecutó OAuth, IA, navegador o un flujo de login con JWT real en esta tarjeta. CI verifica además el arranque sobre su instalación nueva; el estado de su ejecución se registra en el PR.

### Comprobar tokens reales de Auth

Con Auth y Profile saludables, desde la raíz:

```powershell
docker compose -f docker/docker-compose.yml cp scripts/profile/verify_auth_contract.py auth-service:/tmp/profile-auth-contract.py
docker compose -f docker/docker-compose.yml exec -T auth-service python /tmp/profile-auth-contract.py
```

El script solo admite `AUTH_ENV=development`. Crea tres identidades y un tenant sintéticos, usa login y refresh HTTP reales, comprueba aislamiento de rutas incluso para tenant admin/superadmin y prueba revocación por contraseña, desactivación y eliminación. No imprime tokens ni contraseñas; no escribe perfiles ni avatares. El `finally` elimina y verifica sus identidades, tenant y presupuestos de login por cuenta; conserva el presupuesto compartido del origen para respetar la protección de Auth. Los tokens pendientes de sus usuarios se limpian por cascada de Django. No ejecutarlo en producción ni interrumpirlo durante la limpieza.

Las regresiones PostgreSQL usan JWT sintéticos compatibles con Auth, usuarios efímeros y rollback; verifican también que no queden identidades ni perfiles propios de la prueba. Las consultas de identidad que fallen se cierran con 503, sin permitir la operación del perfil. Estos checks no sustituyen las pruebas de concurrencia ni de avatar de las tarjetas siguientes.

Evidencia local de PROFILE-003: **112 pruebas aprobadas**, Ruff sobre app/tests/script, pip check, Compose y enlaces aprobados; auditoría runtime sin avisos conocidos. El contrato HTTP real de arriba pasó con usuario normal, tenant admin y superadmin, login y refresh, cambio de contraseña, cuenta inactiva/eliminada y limpieza verificada. Se conservaron los datos existentes y se usó el volumen sintético de Profile; el estado de CI y la revisión se registran en el PR.

## Diagnóstico PROFILE-001

**Evidencia histórica del 6 de noviembre de 2026, commit `1776a6f`.** Las observaciones de configuración/dependencias/salud siguientes corresponden a esa versión anterior a PROFILE-002 y se conservan para trazar el trabajo pendiente.

Se revisaron todos los módulos del servicio, Dockerfile, dependencias, esquema y trigger compartidos, Compose, identidad/membresías de Auth y consumidores web. La inspección se complementó con sondas TestClient sobre la imagen construida, usando PostgreSQL real del entorno local, clave RSA y usuarios sintéticos. Las escrituras se encerraron en una transacción externa con savepoints y se verificó desde otra conexión que el rollback no dejó perfiles sintéticos. Los archivos se crearon exclusivamente en `/tmp` del contenedor eliminado al terminar. No se utilizaron claves de proveedores, datos personales ni el volumen real de avatares.

### Observaciones reproducidas

| Caso sintético | Resultado en la línea base | Incremento |
| --- | --- | --- |
| Petición sin JWT / token refresh | 401 / 401 | Conservar en PROFILE-003 |
| Access firmado sin `exp`; `exp: null` | 200; 500 respectivamente | PROFILE-003 |
| `user_id` y `sub` distintos; identidad solo `username` | Ambos aceptados, 200 | PROFILE-003 |
| Identidad sin usuario en Auth | GET devuelve perfil vacío, 200; PUT permite crear | PROFILE-003/004 |
| Usuario ordinario consulta otro perfil | 403 | Conservar en PROFILE-003 |
| Tenant admin consulta/modifica un perfil sin relación de tenant | GET y PUT 200 | PROFILE-003 |
| Flag firmado `is_superadmin: "false"` | Se considera verdadero y permite listado, 200 | PROFILE-003 |
| Listado con `limit=1` y dos perfiles sintéticos | Ignora parámetro y devuelve al menos dos | PROFILE-003 |
| Email inválido, teléfono de 10.000 caracteres y URL `javascript:synthetic` | PUT 200; campo desconocido ignorado | PROFILE-004 |
| `email: null` y objeto parcial de metadata | Email conservado; objeto anterior reemplazado | PROFILE-004 |
| Archivo que no es imagen | 400 | Conservar en PROFILE-005 |
| PNG de 2×2 con bytes sintéticos anexos que supera 5 MiB | Upload 200; nombre generado `.png`; bytes originales conservados | PROFILE-005 |
| Descargar ese archivo sin JWT | 200 | PROFILE-005/006 |
| Header Host sintético en upload | Determina el origen de la URL devuelta | PROFILE-002/005 |
| Salud DB y petición con Origin externo | 200 y `Access-Control-Allow-Origin: *` | PROFILE-002 |

Los JWT malformados de estas sondas están **firmados por la clave sintética confiada en el contenedor**. No demuestran falsificación de firmas ni que Auth emita esos claims; demuestran falta de validación defensiva en Profile. El escenario admin no comprobó una matriz completa de tenants activos/revocados; la autorización actual no consulta esas relaciones.

### Riesgos identificados por lectura, todavía sin prueba específica

- La creación usa SELECT y luego INSERT sin resolver carreras sobre `user_id` único. Dos primeras escrituras simultáneas pueden competir; las actualizaciones y la metadata no tienen control de versión. Hace falta prueba con sesiones separadas.
- No hay FK de perfil a Auth ni comprobación de usuario activo. La eliminación de identidad puede dejar perfiles y archivos; se necesita inventario previo y política compatible con los demás escritores.
- El upload hace `file.file.read()` completo; no impone límite propio de bytes, dimensiones, frames o formatos ni recodifica. El spooling de multipart no limita esa lectura final. No se ensayó agotamiento de memoria, bomba de descompresión o carga de gran escala.
- Storage y perfil tienen dos escrituras independientes: subir sin guardar deja archivos y reemplazar no elimina la foto anterior. No existe recuperación ante fallo de disco, compensación o carrera de reemplazos.
- La web limita a 5 MiB, admite `image/*` y URLs externas libres. `<img>` consulta esas URLs directamente; la ruta privada necesitará blob autenticado y limpieza de object URLs. No se comprobó SSRF de servidor ni se afirma que exista.
- AuthProvider conserva el perfil anterior mientras carga una sesión nueva; el GET tiene guardia de desmontaje, pero save/upload no invalidan resultados tardíos por identidad. La página puede repoblar campos al cambiar `currentUser` y usa `innerHTML` como fallback de imagen. Requiere pruebas de sesión, renovación, edición y error; no se afirma una explotación XSS demostrada.
- La matriz visual de permisos deduce acciones por coincidencias de texto y concede todas a `isStaff`. No representa necesariamente los permisos efectivos del tenant activo ni concede permisos en el backend; debe alinearse con los contratos vigentes.
- Excepciones de aplicación reflejan `str(exc)`; errores SQL no están traducidos. Revisar respuestas y logs sin guardar cuerpos ni datos personales. El trigger ya mantiene `updated_at`; no duplicarlo con otra fuente de tiempo sin necesidad.

### Evidencia de herramientas y límites

Comandos ejecutados desde la raíz (proyecto local para no interferir con otras instalaciones):

```powershell
docker compose -f docker/docker-compose.yml -p library008-release build profile-service
docker run --rm --network none library008-release-profile-service python -m pip check
docker run --rm --network none library008-release-profile-service ruff check --no-cache app
docker run --rm --network none library008-release-profile-service python -c 'import os; print(os.geteuid())'
docker compose -f docker/docker-compose.yml config --quiet
```

Build, pip check, Ruff y Compose aprobados; UID observado: **0**. Imagen local: `sha256:f987b0ee524a46832e503bbba47ade6fe3c12703d3eb51675dd1b36eaeb30e37` (manifest list); config `sha256:9dca9055c706ba857d6d16d84636861de4ad32f9626dbcca4f043413a2e7e1c9`. La etiqueta y sus transitivas pueden cambiar al reconstruir; esos identificadores describen esta ejecución.

Las sondas utilizaron `httpx==0.28.1` instalado solo en un contenedor descartable y un script temporal retirado tras documentar resultados. Son evidencia exploratoria, **no una suite permanente ni un gate aprobado de Profile**. PROFILE-002/003/005 incorporarán casos mantenidos y regresiones. No se arrancó el stack completo, no se probó navegador, JWT real de Auth, concurrencia ni restauración de datos en esta tarjeta.

Para auditar se congelaron primero los paquetes de la imagen con `pip freeze > /tmp/baseline.txt`; después se instaló `pip-audit==2.9.0` solo en ese contenedor y se ejecutó `pip-audit --disable-pip --no-deps -r /tmp/baseline.txt`. Reportó **92 avisos en siete paquetes**: cryptography 46.0.6, Pillow 11.2.1, PyJWT 2.12.1, pytest 8.3.5, python-dotenv 1.1.0, python-multipart 0.0.20 y Starlette 0.46.2. Incluye IDs PYSEC/GHSA potencialmente relacionados: no es un conteo de CVE únicos ni prueba de explotación. La mayoría indica versiones corregidas; PYSEC-2026-4146 no muestra corrección. Actualizar el conjunto compatible y reevaluar sin supresiones arbitrarias en PROFILE-002; pytest debe salir de runtime. El SO y copias vendorizadas se escanearán en PROFILE-007. Los seguimientos de imágenes anteriores continúan abiertos en PLAT-002.

## Decisiones propuestas para implementar por incrementos

1. Mantener este servicio pequeño y separado de Auth: contacto/presentación aquí; contraseña, identidad, roles y membresías en Auth. No agregar frameworks, capas ni storage remoto sin una necesidad demostrada.
2. Hacer privado el perfil por dueño, incluso frente a administradores de documentos. La web no consume listado ni perfiles ajenos; retirar esa superficie con una transición explícita. Un directorio empresarial necesitaría una política y respuesta mínima propias, no acceso al perfil personal completo.
3. Validar identidad y vigencia contra Auth sin copiar su modelo de autorización. Definir campos, límites y actualización parcial antes de migrar; conservar datos históricos mediante inventario y reparación explícita.
4. Avatar local asociado al dueño, lectura autenticada y recodificación. Propuesta inicial: hasta 5 MiB para coincidir con la UI; concretar formato, píxeles, dimensiones y frames en PROFILE-005 mediante pruebas. Una operación debe dejar referencia y archivo consistentes o recuperar/limpiar el fallo; inventariar URLs anteriores antes de retirar `/static`. La adaptación mínima del consumidor se entrega junto al cambio de acceso, sin dejar un incremento con avatares rotos; PROFILE-006 completa estados, carreras y experiencia web.
5. Pruebas PostgreSQL y contratos HTTP en CI, consumidor web probado con cambios de sesión, rol DB mínimo e imagen sin root. Cerrar después de validar instalación nueva, actualización y artefacto final con seguimientos visibles.

El orden y los criterios están en [PROFILE-002 a PROFILE-008](../../ROADMAP.md#profileservices). PROFILE-002 incorpora la base de configuración/dependencias/pruebas; este análisis no cierra Profile.

Referencias consultadas: [Agents First Framework](https://github.com/Blandskron/agents-first-repo-docs) para contexto verificable y documentación sin duplicación; [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/#uploadfile) para spooling y lectura; [Pillow Image.verify](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify) para diferenciar verificación de decodificación. Las decisiones se basan en este código y sus sondas, no en una certificación del framework.
