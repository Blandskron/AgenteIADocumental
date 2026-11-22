# CodeSandboxRunner (`code-sandbox-runner`)

Sidecar opcional y endurecido para **Modo 3 — Code Mode** ([ADR-007](../../docs/ADR_CODE_MODE_SANDBOX.md), `AG-010`).

## Controles de aislamiento

- **Sin `eval()`, `exec()` ni `node:vm`:** cada script se ejecuta en un proceso hijo aislado `deno run --deny-all --no-remote --no-npm --no-prompt --v8-flags=--max-old-space-size=128` con `clearEnv: true`.
- **Sin salida a internet ni puertos en host:** opera en una red Docker interna (`internal: true`) accesible únicamente por `agent-orchestrator-service`.
- **Contenedor endurecido:** `read_only: true`, `cap_drop: ["ALL"]`, `security_opt: ["no-new-privileges:true"]`, `mem_limit: 256m`, `cpus: 0.5`, `pids_limit: 64`.
- **Cero secretos:** nunca recibe JWTs, API keys, `DATABASE_URL` ni montaje de `./documents`.
- **Producción multi-tenant:** añadir `runtime: runsc` (gVisor) en el overlay `docker/compose/code-mode.yml`.
