# ADR-005 — Extensibilidad: Proveedores OpenAI-Compatible / Ollama y Superficie MCP de Solo Lectura (`R5-05`)

**Estado:** Aprobado para diseño (previo a implementación)  
**Fecha:** 2026-11-21  
**Ámbito:** `RagDocumentChatServices`, `KnowledgeStudioServices`, `AuthServices`, `docker/`

---

## 1. Proveedores LLM adicionales sobre `LLMProvider`

El puerto `LLMProvider` (`app/application/chat/ports/llm_provider.py`) y la tabla `tenant_integrations(tenant_id, provider, status, config, secrets_encrypted)` permiten incorporar adaptadores adicionales sin duplicar lógica RAG ni de permisos:

1. **`openai_compatible`** (OpenAI, Mistral, vLLM, LiteLLM):
   - Requiere `config.base_url` validado mediante **allowlist estricta anti-SSRF** (solo `https://`, bloqueo de rangos RFC1918 / loopback / link-local `169.254.0.0/16` / metadata cloud `169.254.169.254` salvo perfil local explícito).
   - Mismas reglas de cifrado `secrets1.` y timeout corto en pruebas (`POST /api/integrations/<provider>/test/`).
2. **`ollama` (perfil opcional Compose)**:
   - Nunca se incluye en el `docker/docker-compose.yml` base para no exigir GPU ni desplazar el arranque ligero local.
   - Se habilitará mediante overlay opcional `docker/compose/ollama.yml` con perfil `local-llm`.
3. **Invariante conservado:** `LocalEmbeddingProvider` (`intfloat/multilingual-e5-small`, 384 dims) permanece desacoplado de cualquier proveedor de generación.

---

## 2. Superficie MCP de solo lectura

Cuando se exponga un servidor MCP para agentes externos:

- **Solo lectura** en etapa inicial (`search_documents`, `get_document_chunks`, `list_studio_artifacts`, `get_studio_artifact`).
- **Autenticación obligatoria por token de usuario** (JWT RS256 emitido por `AuthServices`); jamás se usan credenciales maestras ni bypass de permisos multi-tenant.
- **Reutilización de auditoría:** cada invocación MCP registra evento en `audit_logs` con prefijo `mcp.` sin almacenar tokens ni fragmentos privados.
- **Sin prompts paralelos:** MCP consume los mismos contratos de recuperación y plantillas de Studio.

