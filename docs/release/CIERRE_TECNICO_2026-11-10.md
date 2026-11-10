# Cierre técnico local — 10 de noviembre de 2026

El incremento implementa los cambios de instalación y autorización de la [auditoría](AUDITORIA_CIERRE_2026-11-10.md). El recorrido local está verificado. La publicación formal Open Source sigue pendiente de aprobación de licencia/procedencia, una prueba con Groq real y la decisión de versionar/publicar. LICENSE permanece intacto y no se integró código directamente en main.

## Cambios y evidencia

| Hallazgo | Resultado |
| --- | --- |
| C01: aislamiento RAG | Corregido en `VectorRepositoryPgVector._apply_access_filter`: columnas canónicas primero; grupos limitados a empresas vigentes o documentos globales según el contrato de Search. Cuatro regresiones PostgreSQL cubren preguntas/resúmenes, grupo común entre empresas y metadata contradictoria; las pruebas existentes conservan dueño/asignaciones válidas y revocación. |
| C05: autoridad JWT antigua | Siete servicios conservan verificación local de firma/expiración y consultan el `/api/users/me/` existente de Auth. Reemplazan grupos, roles, membresías, permisos y alias con datos actuales; no se añadieron permisos DB ni dependencias. Auth inválido devuelve 401 y una caída/respuesta inválida, 503. Once pruebas nuevas por servicio cubren autoridad retirada, transporte, identidad ajena, tipos inválidos y errores privados. El recorrido HTTP real rechaza cuenta deshabilitada en los siete servicios y un permiso de chat retirado con un JWT previo. |
| C02: administrador | `bootstrap_admin`, ejecutado como `auth_runtime` después de migraciones/integridad. Bloqueo asesor transaccional; validadores Django; ningún secreto en salida. Conserva cualquier superusuario existente, incluso su estado; un nombre ocupado por una cuenta normal no se promueve. Cuatro pruebas PostgreSQL cubren creación, repetición/contraseña intacta, configuración inválida, cuenta ocupada y dos inicializadores concurrentes. |
| C03: almacenamiento | Inicializa solo el propietario de un directorio nuevo vacío y root; no hace cambios recursivos. Un directorio existente inaccesible falla conservando contenido. Access hereda UID/GID de ingesta. Pruebas Linux en contenedor cubren ambos casos y rechazo de UID cero, incluidos sus ceros iniciales. |
| C04/C08: configuración | Contraseña operativa PostgreSQL y clave Django explícitas desde `.env`; sin otro ejemplo de entorno cargado por Auth. Credenciales iniciales solo en el job de bootstrap. pgAdmin queda en perfil opcional y sin contraseña predeterminada. Los valores por rol de la demo local siguen siendo configurables; este Compose no se valida como configuración pública de producción. |
| C06: instalación | Arnés existente ampliado con administrador real, cambio de contraseña, reinicio, segundo arranque y persistencia. Nuevo verificador de clon limpio con volúmenes nuevos, sin eliminar los anteriores; restaura el entorno sintético original al terminar. |
| C07: publicación | README y guías operativas actualizados; CONTRIBUTING.md y SECURITY.md breves. No se sustituyó la reserva de derechos ni se creó una release. La titularidad no se presume únicamente a partir del historial Git. |

Se reutilizó Auth como autoridad mediante su API existente. No se añadió otro servicio de aplicación, framework, dependencia o subsistema de bootstrap. `auth-bootstrap` y `document-storage` son jobs de inicialización. La revisión independiente de seguridad del candidato no encontró un bypass o regresión concreto; la verificación de ejecución se documenta abajo.

## Verificación ejecutada

| Comprobación | Resultado y alcance |
| --- | --- |
| [VERIFICATION.json](VERIFICATION.json) | **88 etapas aprobadas**, cero fallidas: once servicios, roles, suites Python/Ruff, cuatro suites de integridad SQL y carreras, recorrido HTTP, exportación PDF, revocación y persistencia. Código de aplicación `a7ecca1`; el endurecimiento adicional de UID se comprobó aparte y en el clon del commit posterior. |
| [INSTALLATION_CHECK.json](INSTALLATION_CHECK.json) | **22 etapas aprobadas** desde clon local limpio del commit `b2dbb47b3165741de3c8ec2dbaeaec38120b2f37`. Nueva DB/pgvector, claves, esquema/migraciones, administrador, upload/indexación/búsqueda/RAG/PDF, aislamiento, contraseña modificada, reinicios y login web real. Git seguía limpio después de instalar; volúmenes anteriores y nuevos conservados. |
| Frontend | Mismo código y lockfile verificados en la auditoría previa de esta sesión: `npm ci`, 123 pruebas Node, build y 21 Chromium aprobados; `npm audit` sin avisos. El nuevo `browser_probe.mjs` también comprobó el frontend compilado contra Auth/PostgreSQL reales, mediante un puente de bytes Docker sin simular APIs ni publicar puertos. |
| Configuración | Aserciones exactas de CI aprobadas sobre Compose; puertos de producción local en loopback, entorno explícito y montajes de claves. Ejemplo sin contraseña operativa falla claramente antes de arrancar. |
| Almacenamiento | Contenedor efímero sin red ni volúmenes de usuario: directorio nuevo inicializado; directorio no vacío inaccesible rechazado sin modificar contenido/propietario; UID `00` rechazado. |

Los scripts de pruebas y auditoría viven en `scripts/release/`; las instrucciones reproducibles están en el [README de entrega](README.md). Las credenciales sintéticas se generaron en archivos temporales privados a partir de `.env.example`, no en archivos versionados. No se leyó ni montó `.env` personal, Google OAuth o documentos propios. No se ejecutó `down -v`, eliminación de volúmenes ni borrado de bases existentes. La limpieza retiró únicamente fixtures y bases auxiliares creadas por las pruebas; se conserva el administrador de bootstrap sintético.

## Límites y cierre restante

- Embeddings E5, PostgreSQL/pgvector, autenticación, almacenamiento y PDF fueron reales. El transporte de Groq fue determinista y simulado; no acredita disponibilidad/modelo/credenciales del proveedor real. Para completar esa comprobación, usar una clave de desarrollo configurada fuera de Git y un documento sintético.
- Entorno probado: Windows con Docker Desktop y contenedores Linux. No se realizó una instalación separada en un host Linux nativo ni una validación de producción pública.
- El clon y los volúmenes eran nuevos; las construcciones pudieron reutilizar capas de Docker. No se ensayó una descarga completa con la caché de imágenes vacía.
- OAuth Google real permanece opcional y no bloquea esta entrega. OCR avanzado, Graph, MCP, SDK, workflows y otras ampliaciones quedan fuera del cierre.
- La decisión de licencia/procedencia corresponde al titular, conforme al prompt aprobado. Después de cerrar esa decisión, validar Groq y aprobar la versión, recomendar detener el desarrollo funcional de 1.0 y preparar la publicación.

La [reevaluación de imágenes reconstruidas](IMAGE_AUDIT.json) terminó el 2026-11-10T13:13:07.671Z: **12 imágenes, 11 grafos Python válidos, cero CRITICAL, cero correcciones disponibles reportadas y ninguna revisión pendiente según el criterio local**. Filtro: HIGH/CRITICAL, sin supresiones. Conserva 519 coincidencias HIGH del SO (13 CVE únicos): diez backends con 47/11 y la ingesta con 49/13; frontend con cero HIGH/CRITICAL. Esos avisos tienen disposición explícita para la demo local y no equivalen a una aprobación de producción pública.

El primer intento se detuvo por discrepancia entre la etiqueta del frontend y el contenedor restaurado. El verificador de clon se corrigió para forzar recreación al cambiar de contexto; se repitieron sus 22 etapas. Los IDs reconstruidos se reescanearon, y el informe final identifica las imágenes exactas actualmente ejecutadas. No se atribuye un resultado anterior a otro artefacto.

CI retira los JSON anteriores antes de generar sus propios resultados y no publica como suyo el informe local del clon limpio. Las ejecuciones de GitHub deben evaluarse sobre el commit del PR; los enlaces de main en el README conservan su carácter histórico.
