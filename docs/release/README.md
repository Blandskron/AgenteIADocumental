# Verificación de la entrega

Esta carpeta contiene documentación y evidencia JSON; el código de verificación vive en `scripts/release/`. El [tablero](../../ROADMAP.md) registra el estado de entrega y los cierres históricos. Los contratos y la operación de cada servicio siguen en su README.

## Reproducir sin datos personales

Requisitos: Docker Compose reciente (soporte `!reset`/`!override`), Node 24 y acceso a los registros de imágenes y al modelo público de Hugging Face. Desde la raíz:

```sh
docker compose --env-file .env.example -p bd-final-check -f docker/docker-compose.yml -f docker/compose/verification.yml up -d --build --wait blandskron-frontend
node scripts/release/verify.mjs
node scripts/release/audit_images.mjs --project bd-final-check
node scripts/release/verify_graphs.mjs
```

El proyecto dedicado no publica puertos ni monta `.env`, documentos personales o credenciales Google. Usa volúmenes propios y proveedores sintéticos. La ingesta y la recuperación usan el modelo E5 real de 384 dimensiones; solamente la respuesta HTTP de Groq se sustituye por un transporte determinista que lee el contexto recuperado. La prueba comprueba login de dos usuarios, carga, OCR nativo en la suite de ingesta, indexación/reindexación, búsqueda, aislamiento, respuesta con contexto, exportación/lectura PDF y revocación. No equivale a una prueba en vivo de Groq ni de OAuth Google. Drive permanece opcional y deshabilitado.

`VERIFICATION.json` registra etapas, resultado y duración; los comandos de cada etapa están en `scripts/release/verify.mjs` y los logs crudos quedan en un directorio temporal privado. La verificación SQL cubre roles mediante conexiones reales, carreras, jerarquía y ciclo de vida de membresías; las bases auxiliares se retiran incluso ante un fallo de pruebas. `--demo-only` permite repetir el recorrido tras una reconstrucción sin atribuirle las regresiones completas. `--relations-only` repite las cuatro suites SQL. No usar estos scripts contra una instancia con datos propios.

Después de inspeccionar el resultado y comprobar que no quedan fixtures, retirar únicamente el entorno dedicado:

```sh
docker compose --env-file .env.example -p bd-final-check -f docker/docker-compose.yml -f docker/compose/verification.yml down --volumes --remove-orphans
```

## Imágenes y alcance de seguridad

`IMAGE_AUDIT.json` conserva las doce imágenes de aplicación, UID efectivo, inventario de paquetes, entradas de construcción normalizadas a UTF-8/LF, ID inmutable, hash del archivo y config efectivamente escaneada. El escáner Trivy está fijado por digest; no recibe el socket Docker, configuración privada ni archivos de usuarios. La lectura del archivo usa su propietario, sin red ni capabilities. `--resume --work <temporal-propio>` puede reutilizar evidencia solo si coinciden imagen y fuentes. No se aplican supresiones.

El criterio automatizado rechaza críticos, avisos con versión corregida, hallazgos ajenos al SO, instaladores/herramientas de prueba en runtime, UID incorrecto y discrepancias del artefacto. Los avisos HIGH del SO sin corrección indicada se conservan individualmente con disposición explícita para esta demo local en loopback. Esto no significa ausencia de vulnerabilidades ni aprobación para exponer el stack a Internet. Antes de otro despliegue, reconstruir, repetir auditoría y reevaluar los avisos con la base de vulnerabilidades vigente.

Las imágenes Python validan el grafo durante la construcción y retiran `pip` y `ensurepip` del runtime; los targets `test`/`audit` mantienen sus herramientas. Para inspeccionar el runtime se usa `importlib.metadata`, no `pip list`. La ingesta compila Tesseract 5.5.4 desde fuente oficial y checksum fijo, con entrenamiento, archivo y curl deshabilitados; no instala libxml2, libarchive ni libcurl del sistema. Conserva licencia y datos de idioma. El OCR de imágenes continúa cubierto por una prueba real.

## Frontend y actualización

Desde `frontend`: `npm ci`, `npm test`, `npm audit --audit-level=low`, `npm run build`, `npx playwright install chromium` y `npm run test:browser`. Las pruebas de navegador usan contratos HTTP simulados; el recorrido de servicios anterior comprueba persistencia real. Los diálogos nativos mantienen foco/Escape y la sesión descarta respuestas de cuentas/empresas anteriores. La imagen web usa UID 101, raíz de solo lectura y configuración pública en un tmpfs privado; solo recibe variables públicas explícitas.

Para actualizar instalaciones existentes, realizar copia coherente de PostgreSQL, documentos y claves, detener escritores y revisar el preflight antes de aplicar el esquema. No borrar ni reasignar datos heredados para pasar restricciones. El nuevo arranque aplica integridad compartida y, después de Django, `tenant-integrity`; una referencia inconsistente detiene el despliegue. Ver la [guía SQL](../../scripts/database/README.md) y la [operación de Auth](../../backend/AuthServices/docs/OPERATIONS.md). Desplegar API/esquema/web juntos.
