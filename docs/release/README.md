# Verificación de la entrega

El código de verificación vive en [`scripts/release/`](../../scripts/release). Para arrancar y actualizar el stack, consulta la [guía de operación](../operations.md).

## Evidencia del 10 de noviembre de 2026

Los enlaces de esta tabla apuntan al historial de Git. Los reportes generados se escriben en .release-reports/ local, excluido de Git. CI conserva sus reportes en el artefacto release-verification de la ejecución correspondiente.

| Registro | Alcance |
| --- | --- |
| [Verificación local](https://github.com/Blandskron/AgenteIADocumental/blob/c02719bd6adda3eba819ec59d8663f6da5f87c00/docs/release/VERIFICATION.json) | 88 etapas aprobadas sobre `a7ecca1`: contratos, roles, relaciones SQL y recorrido HTTP integral. |
| [Instalación desde clon limpio](https://github.com/Blandskron/AgenteIADocumental/blob/c02719bd6adda3eba819ec59d8663f6da5f87c00/docs/release/INSTALLATION_CHECK.json) | 22 etapas aprobadas sobre `b2dbb47`: volúmenes nuevos, persistencia tras reiniciar y login de la web compilada contra Auth real. |
| [Auditoría local de imágenes](https://github.com/Blandskron/AgenteIADocumental/blob/c02719bd6adda3eba819ec59d8663f6da5f87c00/docs/release/IMAGE_AUDIT.json) | 12 imágenes identificadas por ID, 11 grafos Python validados, cero avisos CRITICAL y cero correcciones disponibles reportadas. El JSON conserva los avisos HIGH del SO y su disposición para la demo local. |

Los resultados corresponden a las revisiones e imágenes identificadas en cada registro. Para la evidencia generada por GitHub Actions, consulta los artefactos de la ejecución correspondiente al commit y la [estrategia de CI/CD y ramas](../CI_CD_STRATEGY.md). [CI Rápido](../../.github/workflows/ci-fast.yml) · [CI Integración y Seguridad](../../.github/workflows/ci-integration.yml) · [Release CD](../../.github/workflows/release.yml) · [CI de la integración transversal](https://github.com/Blandskron/AgenteIADocumental/actions/runs/42730424304) · [CI de main tras esa integración](https://github.com/Blandskron/AgenteIADocumental/actions/runs/42732350270)

## Reproducir sin datos personales

Necesitas Docker Compose con soporte de `!reset`, `!override` y `additional_contexts`, Node 24 y acceso a los registros, las fuentes de construcción y el modelo público. Ejecuta desde la raíz.

```powershell
$env:VERIFICATION_ENV_FILE = node scripts/release/prepare_verification.mjs
docker compose --env-file $env:VERIFICATION_ENV_FILE -p bd-final-check -f docker/docker-compose.yml -f docker/compose/verification.yml up -d --build --wait blandskron-frontend
node scripts/release/verify.mjs
node scripts/release/verify_postgres_upgrade.mjs
node scripts/release/audit_images.mjs --project bd-final-check
node scripts/release/verify_graphs.mjs
```

Para repetir la aceptación desde un clon local limpio y volúmenes nuevos, después de la suite anterior y sin otros checks simultáneos: `node scripts/release/verify_installation.mjs`. Requiere las dependencias de pruebas de frontend (`npm ci` y Chromium instalado) para comprobar también login desde la web compilada contra Auth real. Usa un puente de bytes mediante Docker sin simular las respuestas ni publicar puertos. Genera `.release-reports/INSTALLATION_CHECK.json`, conserva los volúmenes anteriores y nuevos y, si termina correctamente, vuelve a levantar el entorno sintético original. Una ejecución fallida conserva sus coordenadas privadas para diagnóstico; no borrar volúmenes para recuperarla.

El generador parte de `.env.example` y crea un archivo temporal con credenciales sintéticas. Conserva su ruta durante los reinicios y elige un `POSTGRES_DATA_VOLUME` sintético nuevo si ya existe un volumen anterior de la evaluación. Para Bash, usa `export VERIFICATION_ENV_FILE="$(node scripts/release/prepare_verification.mjs)"` y `--env-file "$VERIFICATION_ENV_FILE"`. El proyecto dedicado usa volúmenes de prueba, carece de puertos publicados y mantiene Drive deshabilitado.

La suite genera embeddings reales de 384 dimensiones desde el modelo incluido en las imágenes. La prueba inicial ejecuta ambos proveedores con la red desactivada. El recorrido comprueba login de dos usuarios, carga, OCR, indexación, reindexación, búsqueda, aislamiento, respuesta con contexto, exportación, lectura PDF y revocación. Usa un transporte Groq determinista. OAuth Google se prueba con respuestas sintéticas en la suite de Drive.

La prueba de actualización crea dos clústeres desechables sin red. Comprueba el rechazo del volumen anterior, restaura una copia lógica a PostgreSQL 16 y verifica acceso con un rol restaurado, conservación de los datos y reconstrucción del índice pgvector.

`.release-reports/VERIFICATION.json` registra etapas, resultado y duración; los comandos de cada etapa están en `scripts/release/verify.mjs` y los logs crudos quedan en un directorio temporal privado. La verificación SQL cubre roles mediante conexiones reales, carreras, jerarquía y ciclo de vida de membresías; las bases auxiliares se retiran incluso ante un fallo de pruebas. `--demo-only` permite repetir el recorrido tras una reconstrucción sin atribuirle las regresiones completas. `--relations-only` repite las cuatro suites SQL. No usar estos scripts contra una instancia con datos propios.

El runner comprueba también el login del administrador generado, cambio de contraseña, parada/arranque completo y segundo arranque: deben conservar usuario, hash y documento. El postflight conserva exactamente un administrador de bootstrap y cero usuarios/documentos de prueba. No confundir ese administrador con una fixture sobrante.

Después de inspeccionar el resultado y comprobar que no quedan fixtures, retirar únicamente los contenedores dedicados conservando volúmenes:

```powershell
docker compose --env-file $env:VERIFICATION_ENV_FILE -p bd-final-check -f docker/docker-compose.yml -f docker/compose/verification.yml down --remove-orphans
```

## Imágenes y alcance de seguridad

`.release-reports/IMAGE_AUDIT.json` conserva las doce imágenes de aplicación y la de PostgreSQL, junto con UID efectivo, inventario Python donde corresponde, entradas de construcción, ID inmutable, hash del archivo y configuración escaneada. El escáner Trivy está fijado por digest y recibe los archivos exportados de las imágenes. La lectura del archivo usa su propietario, sin red ni capabilities. `--resume --work <temporal-propio>` puede reutilizar evidencia solo si coinciden imagen y fuentes.

El criterio automatizado rechaza críticos, avisos con versión corregida, hallazgos ajenos al SO, instaladores/herramientas de prueba en runtime, UID incorrecto y discrepancias del artefacto. Los avisos HIGH del SO sin corrección indicada se conservan individualmente con disposición explícita para esta demo local en loopback. Esto no significa ausencia de vulnerabilidades ni aprobación para exponer el stack a Internet. Antes de otro despliegue, reconstruye las imágenes, repite la auditoría y reevalúa los avisos con la base de vulnerabilidades vigente.

Las imágenes Python validan el grafo durante la construcción y retiran `pip` y `ensurepip` del runtime; los targets `test`/`audit` mantienen sus herramientas. Para inspeccionar el runtime se usa `importlib.metadata`, no `pip list`. La ingesta compila Tesseract 5.5.4 desde fuente oficial y checksum fijo, con entrenamiento, archivo y curl deshabilitados; no instala libxml2, libarchive ni libcurl del sistema. Conserva licencia y datos de idioma. El OCR de imágenes continúa cubierto por una prueba real.

## Frontend y actualización

El frontend mantiene sus comandos de verificación en su [guía de desarrollo](../../frontend/docs/DEVELOPMENT.md#verificación). Las pruebas de navegador usan contratos HTTP simulados. El recorrido integral comprueba persistencia real y el verificador de clon comprueba el login web contra Auth. La imagen web usa UID 101, raíz de solo lectura y configuración pública en un tmpfs privado.

Para probar una actualización con datos existentes, sigue el preflight, la copia de seguridad y el orden de despliegue de la [guía de operación](../operations.md#actualizar-una-instalación-existente).
