# 10 — Auditoría Real de Independencia Cloud y Cumplimiento Local-First

- **Filosofía verificada:** 100 % gratuito, open source (MIT), local-first, privacidad de datos y libertad de proveedores.
- **Commit base:** `develop@5a4fac2` (22 de noviembre de 2026).

---

## 1. Matriz de ejecución completamente offline (14 recorridos obligatorios)

| Recorrido | Pregunta de auditoría | Estado real en `develop@5a4fac2` | Evidencia y matices |
|---|---|---|---|
| **1. Registro** | ¿Funciona sin proveedores externos? | **SÍ (100 % offline)** | `POST /api/users/register/` usa PostgreSQL local + `pg_advisory_xact_lock`, sin SMTP ni OIDC. *(Nota: reparar claims iniciales en `_issue_tokens_for_user`.)* |
| **2. Autenticación** | ¿Puede operar localmente? | **SÍ (100 % offline)** | JWT RS256 con claves RSA-2048 autogeneradas localmente (`core/jwt_keys.py`). Google OIDC es 100 % opcional (`503` si deshabilitado). |
| **3. Biblioteca** | ¿Funciona offline? | **SÍ (100 % offline)** | `DocumentLibraryServices`, `DocumentAccessServices` y `DocumentTransferServices` operan íntegramente sobre PostgreSQL + disco local `./documents`. |
| **4. OCR** | ¿Depende de servicios externos? | **SÍ (offline), con brecha funcional** | Tesseract 5.5.4 corre 100 % local en CPU sin red, pero hoy solo incluye `eng.traineddata` (falta `spa.traineddata`) y `PdfExtractor` no invoca OCR en PDFs escaneados. |
| **5. Embeddings** | ¿Se generan localmente? | **SÍ (100 % offline en runtime)** | `intfloat/multilingual-e5-small` (384d) empaquetado en build con verificación SHA-256 y `local_files_only=True`. Cero llamadas externas en runtime. |
| **6. Búsqueda** | ¿Se ejecuta localmente? | **SÍ (100 % offline)** | PostgreSQL 16 + `pgvector` HNSW + FTS GIN + trigram ejecutados completamente en local. |
| **7. Chat RAG** | ¿Funciona con un modelo descargado? | **SÍ (100 % offline tras descarga inicial)** | Con `--profile local-llm` (Ollama en `127.0.0.1:11434`) y un modelo descargado (`qwen2.5:3b`, `llama3.2:3b`), opera sin internet. Groq es estrictamente opcional. |
| **8. Agentes** | ¿Pueden ejecutar tareas con modelos locales? | **PARCIALMENTE (offline en diseño, con bugs activos)** | `AgentOrchestratorServices` soporta Ollama vía `TenantLLMConfigResolver`, pero hoy requiere corregir `AUTH_IDENTITY_URL` en `agents.yml`, persistencia PG y añadir guía JSON al `system_prompt` para modelos 3B–8B. |
| **9. Code Mode** | ¿Opera sin conexión cloud? | **SÍ (100 % offline y air-gapped)** | `CodeSandboxRunner` corre Deno `--deny-all --no-remote --no-npm` en red Docker `code_sandbox_net` con `internal: true` (sin salida a internet). |
| **10. Knowledge Studio** | ¿Puede generar resultados offline? | **NO AÚN (brecha de implementación)** | Validación de groundedness, CSV y SM-2 operan offline, pero `KnowledgeStudioServices` carece de cliente LLM y worker activo, y falla contra PostgreSQL real por el mismatch de `studio.artifacts`. |
| **11. MCP** | ¿Permite uso local autorizado? | **PARCIALMENTE (100 % local)** | `POST /api/v1/mcp` opera localmente con JWT RS256 y 4 tools solo lectura; las 2 tools de artefactos requieren corregir el mismatch SQL de `studio.artifacts`. |
| **12. Exportaciones** | ¿Requieren servicios externos? | **SÍ (100 % offline)** | `DocumentExportServices` usa ReportLab 4.2.5 + fuentes `NotoSans` embebidas en subproceso local; agentes exportan MD/CSV localmente. |
| **13. Auditoría** | ¿Se almacena localmente? | **SÍ en core / ROTO en agentes** | `public.audit_logs` se almacena 100 % en PostgreSQL local; `AgentOrchestratorServices/AuditLogger` requiere corrección de nombres de columna y `GRANT SELECT`. |
| **14. Respaldos** | ¿Pueden restaurarse sin internet? | **SÍ (100 % offline)** | `docker/compose/restore.yml` opera con `network_mode: none` + `restore_postgres16.sh`. Falta un script único de generación de backup para cerrar el ciclo. |

---

## 2. Clasificación estricta de dependencias externas

| Categoría | Dependencias detectadas en el repositorio | Impacto offline | Acción recomendada |
|---|---|---|---|
| **Dependencias de instalación (build-time)** | Docker Hub / GHCR (imágenes base), PyPI, npm, `codeload.github.com` (`pgvector`, `gosu`), compilación Tesseract 5.5.4. | Solo necesarias durante `docker compose build` inicial (o carga de imágenes exportadas con `docker save`/`load`). | Publicar guía de empaquetado offline (`docker save`) y fijar `ollama/ollama` por digest (hoy usa `:latest`). |
| **Dependencias de descarga inicial (one-time)** | `huggingface.co` (`intfloat/multilingual-e5-small`, ~471 MB con SHA-256 en build); registro Ollama al ejecutar `POST /api/integrations/ollama/pull/` (1–5 GB según modelo). | Una vez en imagen/volumen `ollama_models`, **cero acceso a internet en ejecución**. | Mantener `local_files_only=True`; documentar pre-descarga de modelos Ollama para despliegues air-gapped. |
| **Dependencias de ejecución (runtime obligatorio)** | **NINGUNA externa.** Todo el core (PostgreSQL, Auth, Embeddings, Search, Access, Library, Transfer, Conversation, Profile, Export, Frontend con fuente `Inter` local) corre en `127.0.0.1`. | **Autonomía offline total.** | Proteger esta invariante en CI (`ci-integration.yml` y tests de contratos). |
| **Dependencias opcionales (opt-in explícito)** | Groq API (`api.groq.com`), Google Drive / Picker (`apis.google.com`, `accounts.google.com`, `googleapis.com`), Google OIDC JWKS, SMTP (`EMAIL_HOST`), proveedores `openai_compatible` remotos. | Deshabilitadas por defecto; no bloquean arranque ni uso local. | Mover `google-drive-import-service` a un perfil opcional `--profile drive` (hoy se levanta siempre en core consumiendo RAM aunque esté deshabilitado). |
| **Telemetría externa** | **Ninguna encontrada** en frontend ni backend (`sm2-offline.test.js` y auditoría de código confirman ausencia de trackers o beacons externos). | **Privacidad total.** | Mantener política de cero telemetría externa obligatoria. |

---

## 3. Dependencias o fricciones injustificadas detectadas y soluciones

1. **`google-drive-import-service` levantado siempre en Compose core:** Consume contenedor y memoria aun cuando `GOOGLE_DRIVE_ENABLED=false`. **Solución (P1):** Evaluar perfil opcional `--profile drive` (manteniendo compatibilidad con `ci-fast.yml` y `ci-integration.yml`).
2. **`ollama/ollama:latest` sin digest fijado (`docker/compose/ollama.yml`):** Rompe reproducibilidad y auditoría de suministros. **Solución (P1):** Fijar versión/digest explícito igual que `postgres` y `nginx`.
3. **Archivo `brain/.../check_google_oauth.py` rastreado en Git con credencial local:** Riesgo de higiene y seguridad. **Solución (P0):** Retirar del índice Git y agregar `brain/` a `.gitignore`.
4. **Secretos runtime con `chmod 0444` (`docker/scripts/init_secrets.sh`):** Legibles por cualquier UID dentro de contenedores que monten el volumen. **Solución (P1):** Separar secretos por servicio/grupo o permisos `0440` con GID dedicado.
5. **Ausencia de `spa.traineddata` en build de Tesseract:** Obligaría a usuarios hispanohablantes a recurrir a OCR externo para escaneos en español. **Solución (P0):** Incorporar `spa.traineddata` verificado por SHA-256 en build.
6. **Duplicación de ~471 MB de E5 en dos imágenes y ~1.2 GB RAM en runtime:** Dificulta la operación local en equipos de 8 GB RAM. **Solución (P2):** Evaluar compartición interna del servicio de embeddings o carga bajo demanda.
