# Frontend documental

Interfaz React 19, TypeScript estricto y Vite para registro/acceso (incluyendo bootstrap inicial y Google OIDC opcional), biblioteca documental, chat con citas verificables (`SafeMarkdown` anti-XSS), importación por lote Markdown/ZIP, configuración de IA (Groq u Ollama local en `/settings/ai`), Knowledge Studio (`/studio`), auditoría (`/admin/audit`), perfil y administración. Nginx sirve la compilación en Compose sobre loopback (`http://localhost:3000`).

```mermaid
flowchart LR
    app["App, sesión y rutas"] --> pages["Páginas y widgets"]
    pages --> features["Controladores y adaptadores por función"]
    features --> shared["Cliente HTTP, sesión y Design System"]
    shared --> api["APIs locales (8001–8018)"]
```

## Desarrollo local

Con las APIs activas, ejecuta desde este directorio:

```bash
npm ci
npm run dev
```

## Guías

- [Arquitectura de código y convenciones](docs/DEVELOPMENT.md#convenciones).
- [Sistema de diseño y accesibilidad](docs/DEVELOPMENT.md#design-system).
- [Pruebas y compilación](docs/DEVELOPMENT.md#verificación).
- [Instrucciones del frontend](AGENTS.md) y [skill del frontend](../.agents/skills/documental-frontend/SKILL.md).
