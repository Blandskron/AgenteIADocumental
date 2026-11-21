# Auditoria del estado actual — nucleo RAG, Groq, fuentes y grafos

> Estado: auditoría base de planificación (2026-11-21). Las decisiones ejecutables y su seguimiento vivo están consolidados en [roadmap.md](../../../roadmap.md).

Fecha de auditoria: 2026-11-21. Base: rama `main` del repositorio `Blandskron/AgenteIADocumental`, commit local `055a85d` ("Merge pull request #96 from Blandskron/codex/floating-glass-ui"). Todo hallazgo cita ruta y, cuando aporta valor, metodo/linea. Esta auditoria precede a cualquier propuesta de cambio; no modifica codigo.

## 1. Inventario real verificado

- 11 servicios backend + Auth Django, coherentes con `backend/README.md` y el mapa de `docs/architecture.md`:
  - `AuthServices` (8001, Django + SimpleJWT RS256), `RagDocumentChatServices` (8002), `RagDocumentEmbeddingServices` (8003, ingesta), `DocumentSearchServices` (8004), `DocumentAccessServices` (8005), `DocumentLibraryServices` (8006), `DocumentTransferServices` (8007), `ConversationServices` (8008), `ProfileServices` (8015), `DocumentExportServices` (8016), `GoogleDriveImportServices` (8017).
- Frontend React + TypeScript + Vite con arquitectura Feature-Sliced (`frontend/src/{app,entities,features,pages,shared,widgets}`); paginas reales: `AdminPage`, `ApplicationsPage`, `ChatPage`, `DocumentSearchPage`, `LoginPage`, `ProfilePage` (`frontend/src/pages/`). Rutas en `frontend/src/app/router/routes.ts`. No existe hoy ninguna pagina ni feature de "Configuracion" o "Ajustes IA" (busqueda `*setting*|*config*` solo arroja `src/app/config/env.ts`).
- PostgreSQL 16 + pgvector compartido (`documents_db`) con roles por servicio; esquema documental en SQL versionado bajo `scripts/database/` (no en migraciones Django, salvo tablas de identidad).
- Embeddings locales: `intfloat/multilingual-e5-small`, 384 dimensiones, CPU, `local_files_only=True` (`backend/RagDocumentChatServices/app/infrastructure/ai/embedding_provider_local.py:9-16`; mismo patron en ingesta). Modelo empaquetado en la imagen via contexto `e5_model: service:e5-model` (`docker/compose/documents.yml:36-38`), revision fijada `614241f...` citada en README y `backend/RagDocumentChatServices/docs/REFERENCE.md:125`.
- Groq: unico proveedor LLM, usado solo en chat.

## 2. Flujo RAG real (evidencia por ruta)

### 2.1 Ingesta — `RagDocumentEmbeddingServices`
- `POST /api/v1/documents/upload` (`app/interfaces/api/v1/routes/document_routes.py:25`): recibe `UploadFile`, metadata JSON (tope 64 KiB, `form_utils.py:10-21`), resuelve permisos con `require_upload_user` y `build_document_access_metadata`, guarda el original y procesa de forma sincrona por defecto (`process: bool = Form(default=True)`).
- Almacenamiento: `LocalDocumentStorage.save()` sanitiza el nombre (`[^A-Za-z0-9._-]+ -> _`), prefija UUID v4 y abre con modo `xb`, limite 20 MiB (`app/infrastructure/storage/document_storage.py:15-31`, `app/shared/constants.py:4`). Lectura posterior con `LocalDocumentPathResolver.resolve()` que rechaza rutas fuera de la base y esquemas no locales (`document_path_resolver.py:12-29`). Buena postura contra path traversal ya documentada.
- Extractores por MIME (`app/infrastructure/extractors/`): PDF, DOCX, imagenes PNG/JPEG/TIFF con OCR, y `PlainTextExtractor` con `{"text/plain", "text/markdown", "text/csv"}` (`plain_text_extractor.py:7`). Es decir: **Markdown ya se ingiere como texto plano**; no hay parser de frontmatter YAML, wikilinks ni adjuntos, y no hay soporte ZIP.
- Troceado y vectorizacion: `CreateDocumentEmbeddings` (`app/application/embeddings/use_cases/create_document_embeddings.py`) valida dimensionalidad 384 y finitud, trocea con `MAX_CHUNK_SIZE`/`CHUNK_OVERLAP` (por defecto 1200/160, validado `chunk_overlap < max_chunk_size` en `app/config/settings.py`), tope `MAX_DOCUMENT_CHUNKS=2048` y `MAX_EXTRACTED_CHARACTERS=1_000_000`. Reemplazo idempotente por documento via `replace_document_chunks` dentro de `indexing_transaction` (`ingest_existing_document.py:25`).
- Scripts operativos: `scripts/process_pending_documents.py`, `scripts/reindex_documents.py`.

### 2.2 Recuperacion + generacion — `RagDocumentChatServices`
- Unico endpoint de negocio: `POST /api/v1/chat/ask` (`app/interfaces/api/v1/routes/chat_routes.py:10`).
- Autorizacion en dos capas: (1) JWT RS256 verificado localmente y revalidado contra `GET /api/users/me/` de Auth sin proxies ni redirects (`app/config/security.py:98-110`, comentario "never authorize from stale token grants"); (2) permiso explicito `use_chat` en `active_permissions` o superadmin/`*` (`app/interfaces/api/v1/dependencies.py:35`).
- Filtro de acceso **antes** de recuperar: `VectorRepositoryPgVector._apply_access_filter` (`vector_repository_pgvector.py:92-125`) combina propiedad, asignaciones activas, tenant para `TENANT_ADMIN` y grupos; la busqueda usa distancia coseno `<=>` sobre `vector(384)` con `score >= min_score` y `limit` (1..24, `settings.py` + `REFERENCE.md:36`). El resumen por documentos seleccionados alterna fragmentos intercalando `chunk_index` (`get_document_chunks`, lineas 52-90).
- Contexto a Groq: `AskDocumentChat.execute` recorta a `MAX_CONTEXT_CHUNKS` x `MAX_CONTEXT_CHUNK_LENGTH`, historial de hasta 8 preguntas previas recortadas (`chat_history_repository_pg.py`), y llama a `GroqLLMProvider.answer_with_context` (`app/infrastructure/ai/llm_provider_groq.py`): cliente OpenAI con `base_url=https://api.groq.com/openai/v1`, `max_retries=0`, timeout configurable. Errores tipificados: timeout, `AuthenticationError` ("La clave de Groq configurada no es valida"), APIError genericos → `ExternalServiceError` → HTTP 503 (`app/main.py` handler). Sin clave: `GROQ_API_KEY=""` deja `_client=None` y el uso del chat devuelve respuesta de contingencia `ASSISTANT_ERROR_ANSWER` con `sources=[]` (`ask_document_chat.py:24-27,64-65`) — **fallback existente pero opaco**: el usuario ve un mensaje fijo, no un estado "proveedor no configurado".
- Modelo fijo por entorno: `GROQ_CHAT_MODEL=openai/gpt-oss-20b` por defecto (`.env.example`, `settings.py:20`). No hay llamada a `GET /models` de Groq ni validacion de disponibilidad en tiempo de ejecucion (el provider solo expone `answer_with_context`; busqueda `/models` sin resultados en el servicio).

### 2.3 Conversaciones, exportacion y otras fuentes
- `ConversationServices` persiste sesiones/mensajes privados; Exportacion genera PDF desde una instantanea del mensaje con validacion de referencias (`docs/architecture.md`, seccion "De la carga a la respuesta").
- Google Drive es la unica fuente externa: OAuth PKCE S256, importaciones recuperables hacia ingesta, habilitado por `GOOGLE_DRIVE_ENABLED=false` por defecto. Su contrato de rutas (`google_drive_routes.py:19-103`) incluye auth-url, callback, connection status, imports con paginacion e historial. **Este es el patron de referencia para futuros conectores.**

## 3. Gestion de secretos hoy

- Tabla `tenant_integrations` existe en el esquema (`scripts/database/schemas/011_notifications_audit.sql:33-44`): `(tenant_id, provider)` unico, `status ENABLED|DISABLED`, `enabled_for_roles JSONB`, `config JSONB`. Los grep muestran que **ningun servicio la lee o escribe hoy**: esta preparada pero sin consumidor (deuda/diseño adelantado). Es el punto natural de anclaje para configuracion de proveedores IA.
- Cifrado autenticado en reposo ya implementado y probado para tokens Drive: `TokenCipher` (Fernet derivado SHA-256 de secreto, envelope `drive1.<key-id>.<ciphertext>`, llavero de hasta 4 claves, rotacion por `GOOGLE_TOKEN_KEY_ID`/`GOOGLE_TOKEN_PREVIOUS_KEYS`, rechazo explicito de secretos de ejemplo, `ReauthorizationRequired` al descifrar con clave perdida) — `backend/GoogleDriveImportServices/app/infrastructure/google/token_cipher.py`. Documentacion de rotacion en `backend/GoogleDriveImportServices/docs/REFERENCE.md:160`.
- Precedencia actual: puramente `.env` → pydantic-settings con `lru_cache` por proceso (`get_settings()` en ambos servicios RAG). Cambiar `GROQ_API_KEY` exige reiniciar/recargar el contenedor de chat.
- `audit_auth_event` en Auth escribe JSON estructurado a log sin secretos (`users/login_protection.py:17-18`); `AuditedModelViewSet.finalize_response` audita escrituras administrativas (`users/views.py:70-77`). El patron de auditoria sin payload sensible es reutilizable.

## 4. Identidad, permisos y multi-tenant

- Modelo: `Tenant`, `TenantArea` (jerarquia), `TenantMembership` (rol por tenant: ej. `TENANT_ADMIN`), `TenantGroup`, `TenantGroupPermission`, `TenantUserGroup` (`AuthServices/users/models.py`, tablas no gestionadas `managed=False` + SQL en `scripts/database/schemas/003_tenants.sql`).
- `/api/users/me/` entrega `permissions`, `tenant_memberships[].permissions`, `active_tenant_id`, `active_role`, `active_permissions`, `roles` (`serializers.py:102-126`). Superadmin ve `"*"`.
- Los FastAPI services consumen ese perfil en cada operacion (no confian en claims estancos del JWT). Document-level scoping ademas por owner/area/grupos en `metadata` JSONB y columnas dedicadas (`documents.tenant_id`, `owner_user_id`, `owner_area_id`; migracion de metadata a columnas en `001_documents.sql:27-53`).

## 5. Tests relevantes existentes

- `RagDocumentChatServices/tests/test_groq_provider.py`: monkeypatchea el cliente OpenAI y verifica URL real `https://api.groq.com/openai/v1/chat/completions`, payload `model`, y que clave en blanco falla antes de llamar red (fixture sintetico, linea 100-102). **Contrato util para extender pruebas de credenciales.**
- `test_document_access.py`, `test_current_identity.py`: aislamiento de recuperacion segun identidad.
- Suite de liberacion: `scripts/smoke_documental.ps1` y `scripts/release/demo_flow.py` (usa `use_chat`), perfil Compose `verification.yml` con `GROQ_API_KEY: ""` (demo sin proveedor real).
- Auth: `users/tests.py`, `core/test_jwt_keys.py`; BD: `scripts/database/tests/`.

## 6. Discrepancias documentacion vs codigo

1. **Fallback Groq no documentado como estado**: el README/architecture presentan Groq como requisito implicito; el codigo si tolera clave vacia (503/respuesta de contingencia) pero la UX no distingue "sin configurar" de "fallo del proveedor". La documentacion de `operations.md` solo dice "anade GROQ_API_KEY para probar respuestas".
2. **`tenant_integrations` sin uso**: existe en esquema y en `011_notifications_audit.sql` pero ningun modulo la consume; la documentacion no aclara que esta reservada. Riesgo de asumirla operativa.
3. **Markdown soportado parcialmente**: los extractores aceptan `text/markdown` (extrae texto plano), pero ninguna guia lo menciona como tipo de documento de primera clase ni advierte que `[[wikilinks]]`, frontmatter y adjuntos se tratan como literal de texto.
4. **Modelo Groq no validado**: `GROQ_CHAT_MODEL` se acepta tal cual; un ID invalido produce `APIError` generico ("No se pudo generar una respuesta") sin orientar al administrador.
5. **Historial mixto**: `chat_messages` vive tanto en el servicio de chat (repo `ChatHistoryRepositoryPg`) como en `ConversationServices`; la fuente de verdad del historial para prompts es `chat_messages` filtrada por owner (solo preguntas USER, nota en `chat_history_repository_pg.py:14`). Conviene consolidar en el plan Studio/MCP para no duplicar.
6. **Puertos/documentacion**: coherentes entre `backend/README.md`, `docs/architecture.md` y Compose (verificado `documents.yml`). Sin discrepancias de puertos.
7. **Idempotencia de subida**: upload no acepta clave de idempotencia (a diferencia de exportacion, que si usa "clave de operacion" segun architecture.md); reintentos de carga crean documentos duplicados. Relevante para sincronizacion incremental de fuentes (Obsidian/ZIP).

## 7. Mapa de responsabilidades (para extension, no para reemplazo)

| Componente | Responsabilidad real verificada | Candidato a asumir |
| --- | --- | --- |
| `AuthServices` (Django) | Identidad, membresias, permisos, JWT RS256, auditoria de escrituras admin | Autorizacion `manage_ai_settings`; tabla/lectura de integraciones por tenant si se decide alli |
| `RagDocumentChatServices` | Recuperacion autorizada + Groq; settings cacheadas por proceso | Consumo de config de proveedor en caliente (resolver por peticion, no `lru_cache`) |
| `RagDocumentEmbeddingServices` | Upload, almacenamiento seguro, extractores, chunking, E5, reindexacion | Fuente Markdown/ZIP, normalizacion frontmatter/wikilinks, manifiestos de sincronizacion |
| `GoogleDriveImportServices` | OAuth PKCE, conexiones por usuario, imports recuperables | Plantilla de conector (estados, reintentos, historial) para Obsidian/MCP futuro |
| `DocumentSearchServices` / `DocumentAccessServices` / `DocumentLibraryServices` | Busqueda/detalle; contenido, descarga y borrado coordinado; carpetas/favoritos/recientes | Trazabilidad de origen (metadatos `source_*`), limpieza en cascada de relaciones |
| `ConversationServices` / `DocumentExportServices` | Historial privado; PDF con validacion de referencias | Citas con procedencia de grafo/enlaces en exportaciones |
| Frontend | Features por dominio, clientes HTTP por servicio (`shared/api/httpClient.ts`, `session-client.ts`), env publico via `window.__BLANDSKRON_CONFIG__` | Secciones Configuracion > IA, Fuentes y conectores, Indexacion, Relaciones |

## 8. Riesgos heredados a considerar en los planes

- Prompt injection desde contenido indexado hacia el prompt de Groq (el contexto se interpola crudo en `_user_prompt`; solo el system prompt acota rol). Mitigaciones propuestas en `ARCHITECTURE_ADR.md`.
- SSRF inexistente hoy (no hay ingestion por URL) pero introducido por cualquier conector remoto futuro: exigir allowlist y validacion de destino en el servidor.
- ZIP bombs / symlinks: sin soporte ZIP hoy; cualquier opcion que lo introduzca necesita limites descomprimidos, ratio y rechazo de enlaces simbolicos.
- Mezcla multi-tenant en grafos/cache/metadata JSONB: el filtro de acceso debe repetirse en cada nueva superficie (grafo, MCP, exportaciones), no heredar "confianza" del chunk.
- Claves en logs: `configure_logging` registra JSON; asegurar que los endpoints de prueba de credenciales nunca serialicen headers/body con secretos.

## 9. Referencias externas consultadas (fecha 2026-11-21)

- Groq API (OpenAI-compatible, endpoint `/models`, rate limits por org): https://console.groq.com/docs/models y https://console.groq.com/docs/api-reference — disponibles (HTTP 200 al consultar).
- Microsoft GraphRAG: https://github.com/microsoft/graphrag — ultima release observada `v3.3.0`, licencia MIT (GitHub API, 2026-11-21).
- LightRAG (HKUDS): https://github.com/HKUDS/LightRAG — tag mas reciente observado `v1.5.8rc1`, licencia MIT (GitHub API, 2026-11-21).
- Ficha modelo E5 fijada: https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3 (enlazada por README raiz).
- pgvector (ya desplegado): https://github.com/pgvector/pgvector. Postgres para grafos: recursive CTEs / `ltree` / JSONB (documentacion oficial PostgreSQL 16: https://www.postgresql.org/docs/16/).

Nota de proceso: esta auditoria es lectura de codigo y docs del repo local; las URLs externas se verificaron solo como existencia/version/licencia, sin ingestar datos personales ni publicar secretos (todo fixture es sintetico, convencion `AGENTS.md`).
