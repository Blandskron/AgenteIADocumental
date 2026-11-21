# Diseño — Configuracion de IA (Groq) desde la web

Estado: propuesta de planificacion (no implementada). Depende de hallazgos de `CURRENT_STATE_AUDIT.md`. Fecha: 2026-11-21.

## 1. Objetivo y no objetivos

Objetivo: que un administrador configure, valide, reemplace y revoque la API key de Groq y el modelo de generacion desde la web, sin tocar `.env` ni reiniciar contenedores, manteniendo el modo base local intacto cuando no hay proveedor.

No objetivos de esta fase:
- Soporte multi-proveedor completo (OpenAI, Ollama, etc.). Solo se define el contrato que lo permitira despues.
- Cambiar embeddings: `intfloat/multilingual-e5-small` local NO depende de Groq y no debe verse afectado en ningun escenario (ver §3).
- Gestion de claves por usuario final: la configuracion es por tenant/instalacion con autorizacion explicita.

## 2. UX propuesta — `Configuracion > IA`

Nueva pagina (ruta sugerida `/settings/ai`, agrupable bajo `/settings` con subvistas "IA y proveedores", "Fuentes y conectores", "Indexacion", "Relaciones" — ver plan de experiencia en `ARCHITECTURE_ADR.md`). Visible solo con permiso efectivo de administracion de integraciones (§5).

Componentes y estados:

1. **Proveedor "Groq (generacion)"** — tarjeta con:
   - Estado: `no_configurado` | `listo_para_probar` (guardado sin verificar) | `conectado` (ultima prueba OK + timestamp) | `error` (ultima prueba fallo, con motivo categorizado: clave invalida / modelo no disponible / red / timeout).
   - Campo API key: input `type=password`, autocapitalize off, nunca rellena el valor guardado; placeholder `••••••••` + huella corta del secreto (ultimos 4 caracteres del SHA-256, no del secreto). Botones: Guardar, Probar conexion, Revocar.
   - Regla: escribir en el campo = reemplazo total tras "Guardar"; guardar vacio deliberado = revocar.
2. **Modelo**: selector cargado desde la lista de modelos disponibles devuelta por el backend (proxy de `GET https://api.groq.com/openai/v1/models` ejecutado por el servidor, filtrado a modelos chat); permite escribir un ID manualmente marcado como "no verificado". Validacion en "Probar conexion": llamada real minima (`chat.completions.create` con prompt sintetico de 1 token y `max_completion_tokens=1`) contra el modelo elegido. Nunca se envia contenido documental en la prueba.
3. **Parametros avanzados** (opcional, plegado): `max_tokens` (default 2000), `temperature` (0.3), `timeout_seconds` (60) — mapean a los ya existentes `CHAT_COMPLETION_*`.
4. **Separacion clara de capacidades** en la UI: bloque "Vectorizacion e indexacion (local, sin coste de API)" mostrando estado del modelo E5 (presente/ausente, version fijada) como solo lectura, para reforzar visualmente que Groq solo afecta a la generacion de respuestas.
5. **Estados de carga/fallo**: skeleton al cargar config; error de red distingue 401/403 propio (sesion) del resultado de la prueba del proveedor; toast + cambio de badge tras cada accion; historial breve de auditoria visible ("quien, cuando, que accion, resultado" — sin secretos, §6).

Recorrido onboarding objetivo: `docker compose up` → entrar como admin → banner "Conecta tu proveedor de IA" → pegar clave → Probar → "Conectado" → preguntar en el chat. Sin ese paso, el chat sigue operativo en modo degradado (§7).

## 3. Frontera Groq vs E5 local (invariante dura)

Evidencia actual: `LocalEmbeddingProvider` carga SentenceTransformer desde `E5_MODEL_DIR` con `local_files_only=True` en ingesta y chat; `GroqLLMProvider` solo interviene tras la recuperacion. Por tanto:

- Revocar o cambiar la clave Groq jamas puede afectar: upload, extraccion, chunking, embedding, reindexacion, busqueda vectorial ni filtros de acceso. Unicidad garantizada porque comparten proceso pero no dependencias.
- El unico camino degradado es `ask`: recuperacion OK + generacion indisponible → respuesta de contingencia con `sources=[]` hoy; se mejora a estado explícito (§7).
- Riesgo a vigilar en la implementacion: si algun dia se ofrecieran "embeddings de proveedor", debera ser un puerto separado (`EmbeddingProvider`) con su propia config y version de modelo persistida en `document_embeddings.embedding_model`; la migracion de dimensionalidad (precedente: 1536→384 documentado en `docs/operations.md`) queda fuera de esta fase.

## 4. Modelo de datos y secretos

Decision: reutilizar `tenant_integrations` (existe, sin consumidores) en lugar de tabla nueva o microservicio nuevo.

```sql
-- Ilustrativo; la migracion real ira en scripts/database/ con revision propia.
-- provider = 'groq'
-- status   = 'ENABLED' | 'DISABLED'
-- config   = JSONB no sensible: {"model": "...", "max_tokens": 2000,
--            "temperature": 0.3, "timeout_seconds": 60,
--            "last_check": {"at": "...", "result": "ok|auth|model|network"}}
-- secrets_encrypted = JSONB/text: {"api_key": "secrets1.<key_id>.<fernet>"}
-- updated_by, updated_at para trazabilidad de escritura (no del valor)
```

Cambios minimos propuestos a la tabla (evaluables en ADR): columnas `secrets_encrypted TEXT` y `updated_by_user_id TEXT`, o subdocumento cifrado dentro de `config` con envelope. Preferible columna separada para que un `SELECT config` accidental nunca mezcle material cifrado con config legible.

Cifrado:
- Reutilizar el patron `TokenCipher` de Drive (Fernet derivado de secreto maestro, llavero con `key_id` activo + hasta 3 anteriores, rechazo de valores de ejemplo) extraido a utilidad compartida o duplicado deliberadamente con prefijo de dominio `secrets1.`. Fernet es cifrado autenticado (AES-128-CBC + HMAC) → cumple "cifrado autenticado en reposo".
- Clave maestra **fuera de la BD**: variable de entorno `SECRETS_ENCRYPTION_KEY` (+ `SECRETS_KEY_ID`, `SECRETS_PREVIOUS_KEYS`) inyectada por Compose, misma politica documental que `GOOGLE_TOKEN_*` (`GoogleDriveImportServices/docs/REFERENCE.md:160`). Perdida la clave ⇒ las credenciales quedan inutilizables y el sistema reporta `no_configurado/reautenticar`, nunca descifra "por aproximacion".
- Rotacion: escribir con `key_id` activo; descifrar probando el id embebido en el envelope; rotar = anadir clave nueva, re-cifrar al guardar. Sin re-cifrado masivo obligatorio.

Propiedad/ambito: fila por `(tenant_id, provider)`. Instalacion monousuario local: el bootstrap_admin crea/join a un tenant por defecto o se permite `tenant_id IS NULL` como "configuracion de instalacion" reservada a superadmin — decision abierta registrada en el ADR; la recomendacion inicial es **instancia = tenant del admin inicial**, evitando un segundo concepto de ambito.

Que componente la sirve: **AuthServices (Django)** es el dueno natural de `tenants`/`tenant_integrations` y ya audita escrituras administrativas; exponer CRUD restringido + endpoint de prueba que delegue la validacion real a RagDocumentChatServices (o un probe HTTP propio en Auth hacia api.groq.com). Alternativa evaluada y descartada por peso: servicio nuevo dedicado a secretos (una tabla + un cipher no justifican un 12º despliegue). Tambien descartado: que cualquier usuario lea `tenant_integrations` directamente; el chat resuelve la config via una unica llamada interna autenticada o lectura SQL de solo-lectura con rol dedicado `rag_chat_runtime` ampliando grants (preferido: lectura SQL directa de la fila de su tenant, coherente con el modelo de roles por servicio).

## 5. Autorizacion

- Permiso nuevo `manage_ai_settings` en `tenant_group_permissions`/roles (semilla SQL en `scripts/database/seeds` o migration, a definir con el dueno del esquema). Superadmin implicito via `*`.
- Quien ve: `TENANT_ADMIN` con el permiso puede leer config no sensible, escribir clave y probar. Quien no: usuarios normales no ven la seccion (frontend oculta por `active_permissions`, backend rechaza 403 igualmente — el servidor decide, convencion `frontend/AGENTS.md`).
- El chat (`use_chat`) no cambia: consumir la config es interno del servicio, no una capacidad administrable.
- Cross-tenant: toda consulta filtra por `active_tenant_id` resuelto desde Auth en la peticion; prohibido aceptar `tenant_id` del body.

## 6. Endpoints propuestos (contrato)

En AuthServices (estilo DRF existente, OpenAPI decorado como el resto):

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/integrations/groq/` | `{configured, status, model, params, last_check, key_fingerprint}` — **jamais** devuelve la clave |
| PUT | `/api/integrations/groq/credentials/` | body `{"api_key": "..."}` guarda/reemplaza; 201/204; marca `status=listo_para_probar` |
| DELETE | `/api/integrations/groq/credentials/` | revoca (borra ciphertext) |
| PATCH | `/api/integrations/groq/` | actualiza config no sensible (modelo, params) |
| POST | `/api/integrations/groq/test/` | prueba real desde el backend: lista modelos + 1 completcion sintetica minima; responde `{result, models?, reason?}` categorizado |
| GET | `/api/integrations/groq/models/` | proxy server-side de `GET /models` para el selector |

Reglas transversales: TLS no aplica en loopback local pero el diseno debe seguir siendo valido detras de reverse proxy; rate-limit propio del endpoint de prueba (ej. 5/min por usuario, reutilizando el patron `LoginAttemptBudget` de salted-HMAC); timeouts cortos (10 s) distintos del timeout de chat; logs estructurados con `audit_auth_event("ai_settings_write"/"ai_settings_test", actor_id, tenant_id, result)` — sin secretos ni headers.

Frontend: feature nueva `features/settings-ai` con `settings.api.ts` sobre `shared/api/httpClient.ts`; nada de claves en `localStorage`/`sessionStorage` (prohibido expresamente; la clave viaja solo en body de PUT bajo Bearer de sesion). Telemetria inexistente hoy: mantener asi.

## 7. Precedencia, fallback y compatibilidad con `.env`

Orden de resolucion en `RagDocumentChatServices` al construir el provider por peticion (cambiar `build_llm_provider(settings)` para recibir config efectiva):

1. Fila `tenant_integrations(provider='groq', status='ENABLED')` del tenant activo con ciphertext descifrable.
2. `GROQ_API_KEY`/`GROQ_CHAT_MODEL` de entorno (fallback historico; instalaciones existentes siguen funcionando sin migracion).
3. Ninguno → modo `no_configurado`.

Detalles:
- Cache: TTL corto (30–60 s) o invalidacion por evento simple (version/`updated_at` en la fila) para no romper el `lru_cache` de settings globales; la config efectiva por peticion debe poder cambiar sin reinicio.
- Modo `no_configurado`: `POST /chat/ask` responde 200 con senal explicita en el payload (`provider_status: "not_configured"`) o 503 tipificado `{"detail": ..., "code": "PROVIDER_NOT_CONFIGURED"}` — eleccion del equipo de frontend/backend; la UI mostraria "Conecta un proveedor en Configuracion > IA" en lugar del mensaje generico actual. Busqueda, biblioteca e indexacion permanecen 100% operativas.
- Error de clave revocada en caliente: mapear `AuthenticationError` → badge `error(auth)` en Configuracion (el provider ya distingue este caso, `llm_provider_groq.py`).
- Rate limits Groq (por organizacion, observados en docs oficiales 2026-11-21: https://console.groq.com/docs/rate-limits): el chat ya usa `max_retries=0`; se propone propagar `Retry-After`/codigo `RATE_LIMITED` como categoria de error amigable, sin reintento automatico silencioso (coste y frescura de contexto).

## 8. Migracion y rollout

1. Migration SQL: anadir columnas de secretos/auditoria a `tenant_integrations` (additive, reversible con drop de columnas nuevas).
2. Semilla de permiso `manage_ai_settings` para rol admin de tenant.
3. Backend Auth: endpoints §6 + cipher compartido; tests con clave fake tipo fixture (patron `synthetic-test-key` de `test_groq_provider.py`).
4. Chat service: resolver config por peticion con precedencia §7; test de regresion que demuestre que borrar la clave no toca `LocalEmbeddingProvider` (assert de independencia).
5. Frontend: pagina Configuracion > IA con estados §2; Playwright con proveedor simulado (nunca presentar simulado como real, regla `AGENTS.md`).
6. Docs: actualizar README raiz (paso opcional de `.env` GROQ), `docs/operations.md` (nueva clave maestra `SECRETS_ENCRYPTION_KEY` requerida al habilitar la funcion) y `docs/architecture.md`.
7. Rollback: apagar feature flag `AI_SETTINGS_UI=false` → todo vuelve a leer `.env`; los datos guardados permanecen cifrados e inofensivos.

Secretos que siguen siendo necesarios en `.env` al arrancar (no prometer lo contrario): `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `INITIAL_ADMIN_*`, y desde esta fase `SECRETS_ENCRYPTION_KEY` cuando se use config de IA web; ademas los role passwords y paths Compose ya documentados. Lo que deja de ser necesario editar en `.env` para el ciclo diario: `GROQ_API_KEY` y `GROQ_CHAT_MODEL`.

## 9. Extensibilidad futura (sin construirla ahora)

- Contrato `provider` abierto en `tenant_integrations` (`groq`, `openai_compatible`, `ollama`, ...) con `config.base_url` validado por allowlist SSRF cuando exista ingestion URL.
- El puerto interno `LLMProvider` (ya existe como protocolo en `app/application/chat/ports/llm_provider.py`) es el punto de extension: un factory por `provider` reemplaza el import directo de `GroqLLMProvider` en `dependencies.py`.
- Modelos locales (Ollama) quedan fuera: requieren otra topologia de Compose y otra politica de costes; registrar como candidato P2+ con su propio ADR.

## 10. Tareas identificadas (detalle en BACKLOG.md)

P0: cipher compartido + migracion tabla; endpoints Auth; prueba de credenciales; resolutor de config en chat con precedencia; UI Configuracion > IA; tests de independencia E5; docs/operaciones. Criterios de aceptación y pruebas en `BACKLOG.md`.
