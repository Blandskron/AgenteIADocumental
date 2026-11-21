# Colaborar en el frontend

Lee el [README](README.md) y usa la [skill de frontend](../.agents/skills/documental-frontend/SKILL.md) para cambios en UI, sesión o clientes HTTP. La [guía de desarrollo](docs/DEVELOPMENT.md) conserva los comandos y convenciones.

El servidor decide los permisos. Mantén el aislamiento por identidad y tenant, y comprueba teclado, foco y contraste en cambios visuales. Los valores VITE_* son públicos.

Antes de hacer commit en `frontend/`, ejecuta siempre la secuencia completa: `npm run format`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test` y `npm run build` (y `npm run test:browser` cuando el entorno tenga Chromium).
