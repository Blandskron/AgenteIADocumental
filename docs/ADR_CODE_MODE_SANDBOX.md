# ADR-007 — Patrón Code Mode en Sandbox Local Endurecido (Sin `eval`/`exec`/`node:vm` ni Cloudflare Workers)

**Estado:** Aprobado para diseño e implementación en Fase 4 del Roadmap  
**Fecha:** 2026-11-21  
**Ámbito:** `backend/CodeSandboxRunner/`, `backend/AgentOrchestratorServices/`, `docker/compose/code-mode.yml`

---

## 1. Contexto

El patrón **Code Mode** (divulgado por Cloudflare en `@cloudflare/codemode`) permite que un agente LLM descubra definiciones de herramientas bajo demanda y ejecute transformaciones/comparativas programáticas sobre datos autorizados, reduciendo el consumo de tokens de contexto. Sin embargo, adoptar `@cloudflare/codemode` en local exige `wrangler dev` + Miniflare + un stack Node/TypeScript paralelo y la propia documentación advierte que Miniflare local no constituye un sandbox de kernel endurecido para código no confiable.

## 2. Decisión

1. **Adoptar el patrón arquitectónico Code Mode sin dependencia de Cloudflare Workers:**
   - Exponer al agente descubrimiento progresivo de herramientas de solo lectura (`search`, `describe`) y un canal RPC tipado hacia el host (`AgentOrchestratorServices`).
2. **Motor de aislamiento en sidecar dedicado (`code-sandbox-runner`, perfil `--profile code-mode`, `CODE_MODE_ENABLED=false` por defecto):**
   - Runtime consolidado sin permisos OS/red (**Deno `--deny-all`** o **Pyodide/WASM**) ejecutado dentro de un contenedor Docker endurecido (`--read-only`, `--cap-drop ALL`, `security_opt: no-new-privileges:true`, `mem_limit: 256m`, `cpus: 0.5`, `pids_limit: 64`, sin puertos publicados al host y sin acceso a internet).
   - Para despliegues multi-tenant en producción se recomienda añadir runtime de kernel en espacio de usuario (**gVisor / `runsc`**).
3. **Prohibiciones absolutas:**
   - Queda estrictamente prohibido usar `eval()`, `exec()` o `node:vm` como frontera de seguridad.
   - El sandbox **nunca** recibe JWTs, API keys, `DATABASE_URL`, montaje de `./documents` ni Docker Socket.

## 3. Criterios de descarte

- La activación de Code Mode queda bloqueada hasta superar el 100 % de la batería adversarial (`AG-010`: bloqueo de `fetch()` externo, lectura de filesystem/env, bucles infinitos y bombas de memoria).

